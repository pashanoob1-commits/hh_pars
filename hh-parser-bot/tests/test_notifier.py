"""Тесты отправки уведомлений: retry при flood control Telegram."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

from aiogram.exceptions import TelegramBadRequest, TelegramRetryAfter

from bot.services.notifier import MAX_SEND_ATTEMPTS, Notifier


def make_notifier(side_effect):
    bot = SimpleNamespace(send_message=AsyncMock(side_effect=side_effect))
    sleeps: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    return Notifier(bot, sleep=fake_sleep), bot, sleeps


async def test_retry_after_is_retried():
    notifier, bot, sleeps = make_notifier(
        [TelegramRetryAfter(None, "Too Many Requests", 0), None]
    )

    delivered = await notifier.send_vacancy(
        1, "text", vacancy_id="v1", url="https://hh.ru/vacancy/1", employer_id="42"
    )

    assert delivered is True
    assert bot.send_message.await_count == 2
    # retry_after=0 приводим к минимум 1 секунде.
    assert sleeps == [1]


async def test_gives_up_after_max_attempts():
    notifier, bot, sleeps = make_notifier(
        TelegramRetryAfter(None, "Too Many Requests", 0)
    )

    delivered = await notifier.send_vacancy(
        1, "text", vacancy_id="v1", url=None, employer_id=None
    )

    assert delivered is False
    assert bot.send_message.await_count == MAX_SEND_ATTEMPTS
    assert sleeps == [1, 1]


async def test_bad_request_is_not_retried():
    notifier, bot, sleeps = make_notifier(TelegramBadRequest(None, "Bad Request"))

    delivered = await notifier.send_vacancy(
        1, "text", vacancy_id="v1", url=None, employer_id=None
    )

    assert delivered is False
    assert bot.send_message.await_count == 1
    assert sleeps == []
