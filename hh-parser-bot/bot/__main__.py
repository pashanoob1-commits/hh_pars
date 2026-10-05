"""Точка входа: python -m bot."""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from bot.config import Settings, get_settings
from bot.db.database import create_engine, create_session_factory, init_db
from bot.handlers import get_routers
from bot.hh_api.client import HHClient
from bot.middlewares.context import ContextMiddleware
from bot.middlewares.db import DbSessionMiddleware
from bot.scheduler import create_scheduler
from bot.utils.logging_setup import setup_logging
from bot.utils.permissions import apply_data_permissions

logger = logging.getLogger(__name__)


def ensure_sqlite_directory(settings: Settings) -> None:
    """SQLite не создаёт папку сам — готовим каталог для файла БД."""
    if not settings.is_sqlite:
        return
    url = settings.database_url
    marker = "///"
    if marker not in url:
        return
    path = url.split(marker, 1)[1]
    if not path or path == ":memory:":
        return
    Path(path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)


def build_dispatcher(
    settings: Settings, session_factory, hh_client: HHClient
) -> Dispatcher:
    """Собирает диспетчер: роутеры + middleware с зависимостями."""
    dispatcher = Dispatcher(storage=MemoryStorage())
    dispatcher.update.outer_middleware(DbSessionMiddleware(session_factory))
    dispatcher.update.outer_middleware(ContextMiddleware(settings, hh_client))
    for router in get_routers():
        dispatcher.include_router(router)
    return dispatcher


async def main(settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    setup_logging(settings.log_level, settings.log_file)

    if not settings.bot_token:
        raise SystemExit(
            "BOT_TOKEN не задан. Скопируйте .env.example в .env и укажите токен "
            "от @BotFather."
        )

    ensure_sqlite_directory(settings)
    # На PaaS/K8s volume может принадлежать root — готовим каталоги и права.
    apply_data_permissions(settings)

    engine = create_engine(settings)
    await init_db(engine)
    session_factory = create_session_factory(engine)

    hh_client = HHClient(settings)
    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dispatcher = build_dispatcher(settings, session_factory, hh_client)

    scheduler = create_scheduler(
        bot=bot,
        settings=settings,
        session_factory=session_factory,
        client=hh_client,
    )
    scheduler.start()
    logger.info(
        "Бот запущен. Интервал опроса: %s мин, базовая валюта: %s",
        settings.poll_interval_minutes,
        settings.base_currency,
    )

    try:
        await dispatcher.start_polling(bot, allowed_updates=dispatcher.resolve_used_update_types())
    finally:
        scheduler.shutdown(wait=False)
        await hh_client.close()
        await bot.session.close()
        await engine.dispose()
        logger.info("Бот остановлен")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    except SystemExit as exc:
        # SystemExit с сообщением (например, нет BOT_TOKEN) — печатаем и выходим с кодом 1.
        if exc.code:
            print(exc, file=sys.stderr)
            raise SystemExit(1) from None
        raise
