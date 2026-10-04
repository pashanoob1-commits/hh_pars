"""Отправка уведомлений о вакансиях с inline-кнопками."""

from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

logger = logging.getLogger(__name__)

CALLBACK_FAVORITE = "fav"
CALLBACK_HIDE_EMPLOYER = "hide"


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

    def __init__(self, bot: Bot) -> None:
        self._bot = bot

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
        try:
            await self._bot.send_message(
                chat_id=chat_id,
                text=text,
                reply_markup=keyboard,
                disable_web_page_preview=True,
            )
            return True
        except TelegramAPIError as exc:
            logger.warning("Не удалось отправить вакансию %s в чат %s: %s", vacancy_id, chat_id, exc)
            return False
