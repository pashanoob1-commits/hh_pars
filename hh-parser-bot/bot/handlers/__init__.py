"""Все роутеры бота."""

from __future__ import annotations

from aiogram import Router

from bot.handlers import common, favorites, start, stats, stopwords, subscriptions


def get_routers() -> list[Router]:
    """Порядок важен: конкретные callback-ветки идут раньше общих."""
    return [
        start.router,
        subscriptions.router,
        stopwords.router,
        stats.router,
        favorites.router,
        common.router,
    ]


__all__ = ["get_routers"]
