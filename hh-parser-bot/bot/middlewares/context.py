"""Middleware: прокидывает настройки и hh-клиент в хендлеры."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from bot.config import Settings
from bot.hh_api.client import HHClient


class ContextMiddleware(BaseMiddleware):
    """Добавляет в data общие зависимости приложения."""

    def __init__(self, settings: Settings, hh_client: HHClient) -> None:
        self._settings = settings
        self._hh_client = hh_client

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        data["settings"] = self._settings
        data["hh_client"] = self._hh_client
        return await handler(event, data)
