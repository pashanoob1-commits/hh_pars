"""Тесты Alembic-миграций: чистая БД, повторный запуск, baseline старой БД."""

from __future__ import annotations

from sqlalchemy import inspect, select

from bot.config import Settings
from bot.db.database import create_engine, create_session_factory, init_db
from bot.db.migrate import upgrade_database
from bot.db.models import Base, User


def make_settings(tmp_path, *, auto_migrate: bool = True) -> Settings:
    return Settings(
        bot_token="123456:TEST-TOKEN",
        hh_user_agent="hh-parser-bot/1.0 (test@example.com)",
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'migrations.db'}",
        auto_migrate=auto_migrate,
    )


async def test_upgrade_creates_full_schema(tmp_path):
    settings = make_settings(tmp_path)
    engine = create_engine(settings)
    try:
        await init_db(engine, settings)

        async with engine.connect() as connection:
            tables = await connection.run_sync(
                lambda conn: set(inspect(conn).get_table_names())
            )

        assert set(Base.metadata.tables) <= tables
        assert "alembic_version" in tables

        # Мигрированная схема совместима с ORM.
        factory = create_session_factory(engine)
        async with factory() as session:
            session.add(User(telegram_id=12345, username="migrated"))
            await session.commit()
            found = await session.scalar(
                select(User).where(User.telegram_id == 12345)
            )
            assert found is not None and found.username == "migrated"
    finally:
        await engine.dispose()


async def test_legacy_database_is_stamped_without_data_loss(tmp_path):
    # БД, созданная прежними версиями через create_all (без alembic_version).
    settings = make_settings(tmp_path, auto_migrate=False)
    engine = create_engine(settings)
    try:
        await init_db(engine, settings)
        factory = create_session_factory(engine)
        async with factory() as session:
            session.add(User(telegram_id=777, username="legacy"))
            await session.commit()

        await upgrade_database(engine, settings.database_url)

        async with engine.connect() as connection:
            tables = await connection.run_sync(
                lambda conn: set(inspect(conn).get_table_names())
            )
        assert "alembic_version" in tables

        async with factory() as session:
            found = await session.scalar(select(User).where(User.telegram_id == 777))
            assert found is not None and found.username == "legacy"
    finally:
        await engine.dispose()
