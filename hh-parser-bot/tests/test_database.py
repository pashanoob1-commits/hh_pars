"""Тесты доступа к БД: пользователи, подписки, дедупликация, чёрный список."""

from __future__ import annotations

import pytest

from bot.db import repositories as repo
from bot.services.subscriptions import (
    DuplicateSubscription,
    SubscriptionLimitReached,
    SubscriptionService,
)


async def test_get_or_create_user_is_idempotent(session):
    user = await repo.get_or_create_user(session, telegram_id=555, username="vasya")
    again = await repo.get_or_create_user(session, telegram_id=555, username="vasya_new")

    assert user.id == again.id
    assert again.username == "vasya_new"
    await session.commit()

    assert await repo.get_user_by_telegram_id(session, 555) is not None
    assert await repo.get_user_by_telegram_id(session, 999) is None


async def test_subscription_limit(session, settings):
    user = await repo.get_or_create_user(session, telegram_id=1)
    service = SubscriptionService(session, settings)

    for index in range(settings.max_subscriptions_per_user):
        await service.create(
            user.id,
            query=f"python {index}",
            area_id=1,
            area_name="Москва",
        )

    with pytest.raises(SubscriptionLimitReached):
        await service.create(user.id, query="python extra", area_id=1, area_name="Москва")
    await session.commit()


async def test_duplicate_subscription_rejected(session, settings):
    user = await repo.get_or_create_user(session, telegram_id=2)
    service = SubscriptionService(session, settings)

    await service.create(user.id, query="Python", area_id=1, area_name="Москва")
    with pytest.raises(DuplicateSubscription):
        await service.create(user.id, query="python", area_id=1, area_name="Москва")
    # Другой регион — можно
    await service.create(user.id, query="python", area_id=2, area_name="СПб")
    await session.commit()


async def test_subscription_pause_resume_and_delete(session, settings):
    user = await repo.get_or_create_user(session, telegram_id=3)
    service = SubscriptionService(session, settings)
    subscription = await service.create(user.id, query="qa", area_id=1, area_name="Москва")

    assert await service.set_active(user.id, subscription.id, False)
    active = await repo.list_active_subscriptions(session)
    assert subscription.id not in [item.id for item in active]

    assert await service.set_active(user.id, subscription.id, True)
    assert len(await repo.list_active_subscriptions(session)) == 1

    assert await service.set_stop_words(user.id, subscription.id, ["1С", "продажи"])
    updated = await service.get(user.id, subscription.id)
    assert updated.stop_words == ["1С", "продажи"]

    assert await service.delete(user.id, subscription.id)
    assert await repo.list_subscriptions(session, user.id) == []
    await session.commit()


async def test_deduplication_of_sent_vacancies(session):
    user = await repo.get_or_create_user(session, telegram_id=4)
    subscription = await repo.create_subscription(
        session, user.id, query="python", area_id=1, area_name="Москва"
    )

    await repo.mark_sent(
        session,
        user_id=user.id,
        subscription_id=subscription.id,
        vacancy_id="v1",
        payload={"title": "Python dev"},
    )
    await session.commit()

    already = await repo.get_sent_vacancy_ids(session, user.id, ["v1", "v2"])
    assert already == {"v1"}

    payload = await repo.get_sent_payload(session, user.id, "v1")
    assert payload == {"title": "Python dev"}


async def test_favorites_and_blocked_employers(session):
    user = await repo.get_or_create_user(session, telegram_id=5)

    await repo.add_favorite(
        session,
        user.id,
        {
            "vacancy_id": "v100",
            "title": "Go developer",
            "employer_id": "42",
            "employer_name": "Acme",
            "url": "https://hh.ru/vacancy/100",
        },
    )
    # повторное добавление не создаёт дубль
    await repo.add_favorite(session, user.id, {"vacancy_id": "v100", "title": "Go developer"})

    favorites = await repo.list_favorites(session, user.id)
    assert len(favorites) == 1
    assert favorites[0].title == "Go developer"

    blocked = await repo.add_blocked_employer(session, user.id, "42", "Acme")
    await repo.add_blocked_employer(session, user.id, "42", "Acme")
    assert await repo.get_blocked_employer_ids(session, user.id) == {"42"}

    assert await repo.remove_blocked_employer(session, user.id, blocked.id)
    assert await repo.get_blocked_employer_ids(session, user.id) == set()
    await session.commit()


async def test_cascade_delete_user_removes_subscriptions(session):
    user = await repo.get_or_create_user(session, telegram_id=6)
    await repo.create_subscription(
        session, user.id, query="python", area_id=1, area_name="Москва"
    )
    await session.commit()

    await session.delete(user)
    await session.commit()

    assert await repo.list_subscriptions(session, user.id) == []
