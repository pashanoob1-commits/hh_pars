"""Регрессионные тесты кнопок и пользовательского ввода."""

from __future__ import annotations

from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage

from bot.db import repositories as repo
from bot.handlers import favorites as favorites_handler
from bot.handlers import keyboards as kb
from bot.handlers import stats as stats_handler
from bot.handlers import stopwords as stopwords_handler
from bot.handlers import subscriptions as subscriptions_handler
from bot.handlers.states import AddSubscription
from bot.hh_api.models import Area
from bot.services.subscriptions import SubscriptionService
from tests.conftest import make_callback, make_message


def make_state(telegram_id: int = 100) -> FSMContext:
    storage = MemoryStorage()
    key = StorageKey(bot_id=1, chat_id=telegram_id, user_id=telegram_id)
    return FSMContext(storage=storage, key=key)


class AreasClient:
    async def find_areas(self, query, limit=10):
        return [Area(id=123, name="Республика Северная Осетия — Алания")]


async def test_delete_button_uses_clicking_user(session, settings):
    user = await repo.get_or_create_user(session, telegram_id=2001)
    subscription = await SubscriptionService(session, settings).create(
        user.id, query="python", area_id=1, area_name="Москва"
    )
    await session.commit()

    callback = make_callback(f"sub:del:{subscription.id}", telegram_id=2001)
    await subscriptions_handler.cb_delete(callback, session, settings)

    assert await repo.get_subscription(session, user.id, subscription.id) is None
    # Раньше здесь создавался «пользователь-бот» с telegram_id бота.
    assert await repo.get_user_by_telegram_id(session, 999999) is None


async def test_pause_button_uses_clicking_user(session, settings):
    user = await repo.get_or_create_user(session, telegram_id=2002)
    subscription = await SubscriptionService(session, settings).create(
        user.id, query="django", area_id=1, area_name="Москва"
    )
    await session.commit()

    callback = make_callback(f"sub:pause:{subscription.id}", telegram_id=2002)
    await subscriptions_handler.cb_pause(callback, session, settings)

    refreshed = await repo.get_subscription(session, user.id, subscription.id)
    assert refreshed is not None and refreshed.is_active is False


async def test_stats_button_uses_clicking_user(session, settings):
    user = await repo.get_or_create_user(session, telegram_id=2003)
    subscription = await SubscriptionService(session, settings).create(
        user.id, query="python", area_id=1, area_name="Москва"
    )
    await repo.mark_sent(
        session,
        user_id=user.id,
        subscription_id=subscription.id,
        vacancy_id="v1",
        payload={"vacancy_id": "v1", "salary_from": 100000, "salary_to": 200000},
    )
    await session.commit()

    callback = make_callback(f"sub:stats:{subscription.id}", telegram_id=2003)
    await stats_handler.cb_stats(callback, session, settings)

    text = callback.message.answer.await_args.args[0]
    assert "Статистика подписки" in text
    assert "150 000" in text


async def test_unblock_button_uses_clicking_user(session):
    user = await repo.get_or_create_user(session, telegram_id=2004)
    blocker = await repo.add_blocked_employer(session, user.id, "42", "Bad Corp")
    await session.commit()

    callback = make_callback(f"sub:unblock:{blocker.id}", telegram_id=2004)
    await favorites_handler.cb_unblock(callback, session)

    assert await repo.list_blocked_employers(session, user.id) == []

async def test_stopwords_add_button_uses_clicking_user(session, settings):
    user = await repo.get_or_create_user(session, telegram_id=2005)
    subscription = await SubscriptionService(session, settings).create(
        user.id, query="python", area_id=1, area_name="Москва"
    )
    await session.commit()

    state = make_state(2005)
    callback = make_callback(f"sw:add:{subscription.id}", telegram_id=2005)
    await stopwords_handler.cb_add_words(callback, state, session, settings)

    assert await state.get_state() == "StopWordsFlow:waiting_words"
    assert callback.answer.await_count == 1


async def test_remove_favorite_button(session):
    user = await repo.get_or_create_user(session, telegram_id=2006)
    await repo.add_favorite(
        session, user.id, {"vacancy_id": "v9", "title": "QA", "url": "https://hh.ru/vacancy/9"}
    )
    await session.commit()

    callback = make_callback("favdel:v9", telegram_id=2006)
    await favorites_handler.cb_remove_favorite(callback, session)

    assert await repo.list_favorites(session, user.id) == []


async def test_area_search_resets_state_and_callbacks_fit_limit():
    state = make_state(2007)
    await state.set_state(AddSubscription.area_search)
    message = make_message(text="Осетия", telegram_id=2007)

    await subscriptions_handler.wizard_area_search_result(
        message, state, AreasClient()
    )

    # После поиска состояние снова area — иначе кнопки результата не работают.
    assert await state.get_state() == AddSubscription.area.state

    markup = kb.area_search_results_keyboard(
        [(123, "Республика Северная Осетия — Алания")]
    )
    data = markup.inline_keyboard[0][0].callback_data
    assert len(data.encode("utf-8")) <= 64


async def test_area_picked_takes_name_from_state():
    state = make_state(2008)
    await state.set_state(AddSubscription.area)
    await state.update_data(area_options={"123": "Республика Северная Осетия — Алания"})

    callback = make_callback("wiz:area:123", telegram_id=2008)
    await subscriptions_handler.wizard_area_picked(callback, state)

    data = await state.get_data()
    assert data["area_id"] == 123
    assert data["area_name"] == "Республика Северная Осетия — Алания"
    assert await state.get_state() == AddSubscription.experience.state


async def test_user_input_is_html_escaped(session, settings):
    user = await repo.get_or_create_user(session, telegram_id=2009)
    await SubscriptionService(session, settings).create(
        user.id, query="<script>python</script>", area_id=1, area_name="A&B"
    )
    await session.commit()

    message = make_message(text="/list", telegram_id=2009)
    await subscriptions_handler.cmd_list(message, session, settings)

    text = message.answer.await_args_list[-1].args[0]
    assert "<script>" not in text
    assert "&lt;script&gt;" in text
    assert "A&amp;B" in text




def test_keyboard_texts_fit_telegram_limit():
    from bot.db.models import Subscription

    sub = Subscription(
        id=1, user_id=1, query="q" * 100, area_id=1, area_name="a" * 100
    )
    markup = kb.subscriptions_keyboard([sub], "del")
    assert len(markup.inline_keyboard[0][0].text) <= 64

    blocked = kb.blocked_employers_keyboard([(1, "b" * 100)])
    assert len(blocked.inline_keyboard[0][0].text) <= 64
