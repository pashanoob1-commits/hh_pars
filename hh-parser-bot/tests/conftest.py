"""Общие фикстуры тестов."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from bot.config import Settings
from bot.db.database import create_engine, create_session_factory, init_db


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(
        bot_token="123456:TEST-TOKEN",
        hh_user_agent="hh-parser-bot/1.0 (test@example.com)",
        hh_api_base="https://api.hh.ru",
        hh_min_request_interval=0.0,
        hh_max_retries=3,
        hh_per_page=10,
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'test.db'}",
        base_currency="RUR",
        poll_interval_minutes=15,
        first_run_limit=2,
        max_subscriptions_per_user=3,
        currency_cache_hours=24,
    )


@pytest.fixture
async def engine(settings):
    engine = create_engine(settings)
    await init_db(engine)
    yield engine
    await engine.dispose()


@pytest.fixture
async def session_factory(engine):
    return create_session_factory(engine)


@pytest.fixture
async def session(session_factory):
    async with session_factory() as session:
        yield session
        await session.commit()


def make_message(text: str = "", telegram_id: int = 100, username: str = "tester"):
    """Поддельное сообщение aiogram с AsyncMock-методами."""
    message = SimpleNamespace()
    message.text = text
    message.from_user = SimpleNamespace(
        id=telegram_id, username=username, full_name="Test User"
    )
    message.answer = AsyncMock()
    message.reply = AsyncMock()
    return message


def make_callback(data: str, telegram_id: int = 100, text: str = "message"):
    """Поддельный callback query."""
    callback = SimpleNamespace()
    callback.data = data
    callback.from_user = SimpleNamespace(id=telegram_id, username="tester", full_name="Test")
    callback.answer = AsyncMock()

    message = SimpleNamespace()
    message.text = text
    message.html_text = text
    message.from_user = callback.from_user
    message.answer = AsyncMock()
    message.edit_text = AsyncMock()
    message.answer_document = AsyncMock()
    callback.message = message
    return callback
