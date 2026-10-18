"""Запуск Alembic-миграций из приложения и командной строки.

CLI:
    python -m bot.db.migrate upgrade
    python -m bot.db.migrate downgrade
    python -m bot.db.migrate current

URL берётся из DATABASE_URL/.env; alembic.ini для этого не обязателен.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import AsyncEngine

logger = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"


def make_config(database_url: str) -> Config:
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    # ConfigParser интерполирует «%», поэтому экранируем его в URL.
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    return config


async def upgrade_database(engine: AsyncEngine, database_url: str) -> None:
    """Применяет миграции до head.

    Если БД создана прошлыми версиями через create_all (нет alembic_version,
    но таблицы уже есть), сначала фиксируем текущую схему как базовую.
    """
    config = make_config(database_url)

    async with engine.connect() as connection:
        has_version = await connection.run_sync(
            lambda conn: inspect(conn).has_table("alembic_version")
        )
        has_users = await connection.run_sync(
            lambda conn: inspect(conn).has_table("users")
        )

    if has_users and not has_version:
        logger.info("БД без alembic_version — помечаю текущую схему как базовую")
        await asyncio.to_thread(command.stamp, config, "head")

    await asyncio.to_thread(command.upgrade, config, "head")


async def downgrade_database(database_url: str, revision: str = "base") -> None:
    await asyncio.to_thread(command.downgrade, make_config(database_url), revision)


async def current_revision(database_url: str) -> None:
    await asyncio.to_thread(command.current, make_config(database_url))


async def _run(action: str, revision: str) -> None:
    from bot.config import get_settings
    from bot.db.database import create_engine

    settings = get_settings()
    engine = create_engine(settings)
    try:
        if action == "upgrade":
            await upgrade_database(engine, settings.database_url)
        elif action == "downgrade":
            await downgrade_database(
                settings.database_url, "base" if revision == "head" else revision
            )
        else:
            await current_revision(settings.database_url)
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Alembic-миграции hh-parser-bot")
    parser.add_argument(
        "action", choices=["upgrade", "downgrade", "current"], nargs="?", default="upgrade"
    )
    parser.add_argument("revision", nargs="?", default="head")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    asyncio.run(_run(args.action, args.revision))


if __name__ == "__main__":
    main()
