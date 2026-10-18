"""Отправка уведомлений о вакансиях с inline-кнопками."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramRetryAfter
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

logger = logging.getLogger(__name__)

CALLBACK_FAVORITE = "fav"
CALLBACK_HIDE_EMPLOYER = "hide"

# Сколько раз пробуем отправить одно сообщение при flood control Telegram.
MAX_SEND_ATTEMPTS = 3


def build_vacancy_keyboard(
    vacancy_id: str, url: str | None, employer_id: str | None
) -> InlineKeyboardMarkup | None:
    """Кнопки под уведомлением: откликнуться / в избранное / скрыть компанию."""
    rows: list[list[InlineKeyboardButton]] = []

    if url:
        rows.append(
            [InlineKeyboardButton(text="🔥 Откликнуться", url=url)]
        )

    actions: list[InlineKeyboardButton] = [
        InlineKeyboardButton(
            text="⭐ В избранное", callback_data=f"{CALLBACK_FAVORITE}:{vacancy_id}"
        )
    ]
    if employer_id:
        actions.append(
            InlineKeyboardButton(
                text="🚫 Скрыть компанию",
                callback_data=f"{CALLBACK_HIDE_EMPLOYER}:{vacancy_id}",
            )
        )
    rows.append(actions)

    if not rows:
        return None
    return InlineKeyboardMarkup(inline_keyboard=rows)


class Notifier:
    """Обёртка над Bot для отправки уведомлений с логированием ошибок."""

    def __init__(
        self,
        bot: Bot,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._bot = bot
        self._sleep = sleep

    async def send_vacancy(
        self,
        chat_id: int,
        text: str,
        *,
        vacancy_id: str,
        url: str | None,
        employer_id: str | None,
    ) -> bool:
        keyboard = build_vacancy_keyboard(vacancy_id, url, employer_id)

        for attempt in range(1, MAX_SEND_ATTEMPTS + 1):
            try:
                await self._bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    reply_markup=keyboard,
                    disable_web_page_preview=True,
                )
                return True
            except TelegramRetryAfter as exc:
                # Telegram flood control: ждём указанное время и пробуем снова,
                # иначе вакансия потеряется (watermark подписки уже сдвинется).
                delay = max(int(getattr(exc, "retry_after", 1)), 1)
                if attempt >= MAX_SEND_ATTEMPTS:
                    logger.warning(
                        "Flood control: вакансия %s в чат %s не отправлена после %s попыток",
                        vacancy_id,
                        chat_id,
                        attempt,
                    )
                    return False
                logger.info(
                    "Flood control: ждём %s с перед повтором (вакансия %s, чат %s)",
                    delay,
                    vacancy_id,
                    chat_id,
                )
                await self._sleep(delay)
            except TelegramAPIError as exc:
                logger.warning(
                    "Не удалось отправить вакансию %s в чат %s: %s",
                    vacancy_id,
                    chat_id,
                    exc,
                )
                return False

        return False
