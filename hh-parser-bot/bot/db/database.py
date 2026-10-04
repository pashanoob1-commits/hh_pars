"""Подключение к БД: async engine, фабрика сессий, создание схемы.

Диалект не прошит в коде: SQLite/PgSQL/MySQL выбираются через DATABASE_URL.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from bot.config import Settings
from bot.db.models import Base

logger = logging.getLogger(__name__)


def create_engine(settings: Settings) -> AsyncEngine:
    """Создаёт async-движок по DATABASE_URL."""
    engine = create_async_engine(settings.database_url, future=True)

    if settings.is_sqlite:
        # SQLite по умолчанию не проверяет внешние ключи — включаем.
        @event.listens_for(engine.sync_engine, "connect")
        def _enable_sqlite_fk(dbapi_connection, _record) -> None:  # pragma: no cover
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False, autoflush=False)


async def init_db(engine: AsyncEngine) -> None:
    """Создаёт отсутствующие таблицы (простейшая миграция для MVP)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Схема БД готова")


async def session_scope(
    factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    """Контекстный менеджер сессии с commit/rollback."""
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
