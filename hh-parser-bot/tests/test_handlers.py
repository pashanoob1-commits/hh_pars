"""Базовые тесты команд бота (хендлеры вызываются напрямую)."""

from __future__ import annotations

from aiogram.filters import CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage

from bot.db import repositories as repo
from bot.handlers import common as common_handler
from bot.handlers import favorites as favorites_handler
from bot.handlers import start as start_handler
from bot.handlers import stopwords as stopwords_handler
from bot.handlers import subscriptions as subscriptions_handler
from bot.handlers.states import AddSubscription
from bot.hh_api.models import HHVacancy
from bot.services.subscriptions import SubscriptionService

from tests.conftest import make_callback, make_message


def make_state(telegram_id: int = 100) -> FSMContext:
    storage = MemoryStorage()
    key = StorageKey(bot_id=1, chat_id=telegram_id, user_id=telegram_id)
    return FSMContext(storage=storage, key=key)


class StubClient:
    async def find_areas(self, query, limit=10):
        return []

    async def get_vacancy(self, vacancy_id):
        return None


async def test_start_registers_user(session, settings):
    message = make_message(text="/start", telegram_id=777)
    await start_handler.cmd_start(message, session, settings)

    user = await repo.get_user_by_telegram_id(session, 777)
    assert user is not None
    assert "Привет" in message.answer.await_args.args[0]


async def test_help_lists_commands(session):
    message = make_message(text="/help")
    await start_handler.cmd_help(message)

    text = message.answer.await_args.args[0]
    for command in ("/add", "/list", "/stopwords", "/stats"):
        assert command in text


async def test_add_wizard_starts(session, settings):
    message = make_message(text="/add", telegram_id=778)
    state = make_state(778)

    await subscriptions_handler.cmd_add(message, state, session, settings)

    assert await state.get_state() == AddSubscription.query.state
    assert "Шаг 1" in message.answer.await_args.args[0]


async def test_add_wizard_blocked_by_limit(session, settings):
    user = await repo.get_or_create_user(session, telegram_id=779)
    service = SubscriptionService(session, settings)
    for index in range(settings.max_subscriptions_per_user):
        await service.create(user.id, query=f"q{index}", area_id=1, area_name="Москва")

    message = make_message(text="/add", telegram_id=779)
    state = make_state(779)
    await subscriptions_handler.cmd_add(message, state, session, settings)

    assert "лимит" in message.answer.await_args.args[0].lower()
    assert await state.get_state() is None


async def test_add_wizard_query_then_region_step(session):
    message = make_message(text="python backend", telegram_id=780)
    state = make_state(780)
    await state.set_state(AddSubscription.query)

    await subscriptions_handler.wizard_query(message, state)

    assert await state.get_state() == AddSubscription.area.state
    data = await state.get_data()
    assert data["query"] == "python backend"


async def test_list_shows_subscriptions(session, settings):
    user = await repo.get_or_create_user(session, telegram_id=781)
    await SubscriptionService(session, settings).create(
        user.id, query="python", area_id=1, area_name="Москва"
    )

    message = make_message(text="/list", telegram_id=781)
    await subscriptions_handler.cmd_list(message, session, settings)

    assert "Ваши подписки" in message.answer.await_args_list[0].args[0]


async def test_stopwords_command_add_and_clear(session, settings):
    user = await repo.get_or_create_user(session, telegram_id=782)
    subscription = await SubscriptionService(session, settings).create(
        user.id, query="python", area_id=1, area_name="Москва"
    )

    message = make_message(text="/stopwords", telegram_id=782)
    command = CommandObject(
        prefix="/", command="stopwords", args=f"{subscription.id} add 1С, продажи"
    )
    await stopwords_handler.cmd_stopwords(message, session, settings, command)

    service = SubscriptionService(session, settings)
    assert (await service.get(user.id, subscription.id)).stop_words == ["1с", "продажи"]

    clear = CommandObject(prefix="/", command="stopwords", args=f"{subscription.id} clear")
    await stopwords_handler.cmd_stopwords(
        make_message(text="/stopwords", telegram_id=782), session, settings, clear
    )
    assert (await service.get(user.id, subscription.id)).stop_words == []


async def test_hide_employer_button_blocks_company(session):
    user = await repo.get_or_create_user(session, telegram_id=783)
    subscription = await repo.create_subscription(
        session, user.id, query="python", area_id=1, area_name="Москва"
    )
    await repo.mark_sent(
        session,
        user_id=user.id,
        subscription_id=subscription.id,
        vacancy_id="v1",
        payload={
            "vacancy_id": "v1",
            "employer_id": "42",
            "employer_name": "Bad Corp",
            "title": "Python dev",
        },
    )
    await session.commit()

    callback = make_callback("hide:v1", telegram_id=783)
    await common_handler.cb_hide_employer(callback, session, StubClient())

    assert await repo.get_blocked_employer_ids(session, user.id) == {"42"}
    assert "скрыта" in callback.message.edit_text.await_args.args[0]


async def test_favorite_button_adds_favorite(session):
    user = await repo.get_or_create_user(session, telegram_id=784)
    subscription = await repo.create_subscription(
        session, user.id, query="python", area_id=1, area_name="Москва"
    )
    await repo.mark_sent(
        session,
        user_id=user.id,
        subscription_id=subscription.id,
        vacancy_id="v2",
        payload={"vacancy_id": "v2", "title": "Go dev", "employer_name": "Acme"},
    )
    await session.commit()

    callback = make_callback("fav:v2", telegram_id=784)
    await common_handler.cb_favorite(callback, session, StubClient())

    favorites = await repo.list_favorites(session, user.id)
    assert [item.vacancy_id for item in favorites] == ["v2"]


async def test_favorites_and_unblock_commands(session):
    user = await repo.get_or_create_user(session, telegram_id=785)
    await repo.add_favorite(
        session, user.id, {"vacancy_id": "v9", "title": "QA", "employer_name": "QA Inc"}
    )
    await repo.add_blocked_employer(session, user.id, "77", "Blocked Inc")
    await session.commit()

    favorites_message = make_message(text="/favorites", telegram_id=785)
    await favorites_handler.cmd_favorites(favorites_message, session)
    assert "Избранное" in favorites_message.answer.await_args_list[0].args[0]

    unblock_message = make_message(text="/unblock", telegram_id=785)
    command = CommandObject(prefix="/", command="unblock", args=None)
    await favorites_handler.cmd_unblock(unblock_message, session, command)
    assert "Чёрный список" in unblock_message.answer.await_args.args[0]


def test_hh_vacancy_searchable_text():
    vacancy = HHVacancy(
        id="1",
        name="Python Dev",
        snippet_requirement="Django",
        snippet_responsibility=None,
    )
    assert vacancy.searchable_text == "python dev django"
