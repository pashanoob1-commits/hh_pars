"""Тесты планировщика: дедупликация, стоп-слова, чёрный список, first_run_limit."""

from __future__ import annotations

from datetime import timedelta

from bot.db import repositories as repo
from bot.hh_api.models import HHVacancy
from bot.scheduler.poller import VacancyPoller
from bot.utils.time import utcnow


def vacancy(
    vacancy_id: str,
    *,
    name: str = "Python разработчик",
    employer_id: str = "1",
    requirement: str | None = "Python, FastAPI",
    published_at=None,
) -> HHVacancy:
    return HHVacancy(
        id=vacancy_id,
        name=name,
        employer_id=employer_id,
        employer_name=f"Company {employer_id}",
        salary_from=100000,
        salary_to=150000,
        salary_currency="RUR",
        snippet_requirement=requirement,
        alternate_url=f"https://hh.ru/vacancy/{vacancy_id}",
        published_at=published_at or (utcnow() - timedelta(hours=1)),
    )


class FakeClient:
    """Фейковый HHClient: отдаёт заранее подготовленные вакансии по тексту запроса."""

    def __init__(self, results: dict[str, list[HHVacancy]]) -> None:
        self.results = results
        self.search_calls = 0

    async def search_vacancies(self, params):
        self.search_calls += 1
        return list(self.results.get(params.text, []))

    async def get_currency_rates(self):
        return {"RUR": 1.0}


class StubNotifier:
    def __init__(self, deliver: bool = True) -> None:
        self.deliver = deliver
        self.sent: list[str] = []

    async def send_vacancy(self, chat_id, text, *, vacancy_id, url, employer_id):
        if self.deliver:
            self.sent.append(vacancy_id)
        return self.deliver


def make_poller(settings, session_factory, client, notifier) -> VacancyPoller:
    poller = VacancyPoller(
        bot=None, settings=settings, session_factory=session_factory, client=client
    )
    poller._notifier = notifier  # noqa: SLF001 — подменяем отправку в тестах
    return poller


async def test_first_run_limit_and_watermark(session, session_factory, settings):
    """Первый запуск ограничен first_run_limit; далее watermark отсекает старое."""
    user = await repo.get_or_create_user(session, telegram_id=1001)
    await repo.create_subscription(
        session, user.id, query="python", area_id=1, area_name="Москва"
    )
    await session.commit()

    client = FakeClient({"python": [vacancy("v1"), vacancy("v2"), vacancy("v3")]})
    notifier = StubNotifier()
    poller = make_poller(settings, session_factory, client, notifier)

    sent_first = await poller.poll_once()
    assert sent_first == settings.first_run_limit == 2
    assert notifier.sent == ["v1", "v2"]

    # Вторая проверка: вакансии опубликованы до watermark -> ничего нового.
    sent_second = await poller.poll_once()
    assert sent_second == 0
    assert notifier.sent == ["v1", "v2"]


async def test_dedup_prevents_resending_already_sent_vacancy(session, session_factory, settings):
    user = await repo.get_or_create_user(session, telegram_id=1006)
    subscription = await repo.create_subscription(
        session, user.id, query="python", area_id=1, area_name="Москва"
    )
    # Вакансия v1 уже отправлялась ранее (свежая по дате публикации).
    await repo.mark_sent(
        session,
        user_id=user.id,
        subscription_id=subscription.id,
        vacancy_id="v1",
        payload={"vacancy_id": "v1"},
    )
    await session.commit()

    fresh = utcnow() + timedelta(hours=1)
    client = FakeClient(
        {"python": [vacancy("v1", published_at=fresh), vacancy("v2", published_at=fresh)]}
    )
    notifier = StubNotifier()
    poller = make_poller(settings, session_factory, client, notifier)

    assert await poller.poll_once() == 1
    assert notifier.sent == ["v2"]


async def test_stop_words_and_blocked_employers_are_filtered(session, session_factory, settings):
    user = await repo.get_or_create_user(session, telegram_id=1002)
    subscription = await repo.create_subscription(
        session,
        user.id,
        query="python",
        area_id=1,
        area_name="Москва",
        stop_words=["senior"],
    )
    await repo.add_blocked_employer(session, user.id, "42", "Bad Corp")
    await session.commit()

    client = FakeClient(
        {
            "python": [
                vacancy("keep"),
                vacancy("senior_only", name="Senior Python developer"),
                vacancy("blocked", employer_id="42"),
            ]
        }
    )
    notifier = StubNotifier()
    poller = make_poller(settings, session_factory, client, notifier)

    sent = await poller.poll_once()

    assert sent == 1
    assert notifier.sent == ["keep"]
    assert subscription.stop_words == ["senior"]


async def test_dedup_across_subscriptions_of_same_user(session, session_factory, settings):
    user = await repo.get_or_create_user(session, telegram_id=1003)
    await repo.create_subscription(
        session, user.id, query="python", area_id=1, area_name="Москва"
    )
    await repo.create_subscription(
        session, user.id, query="django", area_id=1, area_name="Москва"
    )
    await session.commit()

    shared = vacancy("shared")
    client = FakeClient({"python": [shared], "django": [shared]})
    notifier = StubNotifier()
    poller = make_poller(settings, session_factory, client, notifier)

    sent = await poller.poll_once()

    assert sent == 1
    assert notifier.sent == ["shared"]


async def test_paused_subscription_is_skipped(session, session_factory, settings):
    user = await repo.get_or_create_user(session, telegram_id=1004)
    subscription = await repo.create_subscription(
        session, user.id, query="python", area_id=1, area_name="Москва"
    )
    subscription.is_active = False
    await session.commit()

    client = FakeClient({"python": [vacancy("v1")]})
    notifier = StubNotifier()
    poller = make_poller(settings, session_factory, client, notifier)

    assert await poller.poll_once() == 0
    assert client.search_calls == 0


async def test_failed_delivery_is_not_marked_as_sent(session, session_factory, settings):
    user = await repo.get_or_create_user(session, telegram_id=1005)
    await repo.create_subscription(
        session, user.id, query="python", area_id=1, area_name="Москва"
    )
    await session.commit()

    client = FakeClient({"python": [vacancy("v1")]})
    notifier = StubNotifier(deliver=False)
    poller = make_poller(settings, session_factory, client, notifier)

    assert await poller.poll_once() == 0

    subscriptions = await repo.list_subscriptions(session, user.id)
    records = await repo.list_sent_for_subscription(session, user.id, subscriptions[0].id)
    assert records == []
    assert subscriptions[0].last_checked_at is not None
