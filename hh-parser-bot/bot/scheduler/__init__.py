"""Планировщик опроса подписок (APScheduler)."""

from __future__ import annotations

import logging

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.config import Settings
from bot.hh_api.client import HHClient
from bot.scheduler.poller import VacancyPoller

logger = logging.getLogger(__name__)


def create_scheduler(
    *,
    bot: Bot,
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
    client: HHClient,
) -> AsyncIOScheduler:
    """Создаёт планировщик с задачей периодического опроса подписок."""
    poller = VacancyPoller(
        bot=bot, settings=settings, session_factory=session_factory, client=client
    )
    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(
        poller.poll_once,
        trigger="interval",
        minutes=settings.poll_interval_minutes,
        id="poll_subscriptions",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=300,
    )
    logger.info(
        "Планировщик создан: интервал опроса %s мин", settings.poll_interval_minutes
    )
    return scheduler


__all__ = ["VacancyPoller", "create_scheduler"]
