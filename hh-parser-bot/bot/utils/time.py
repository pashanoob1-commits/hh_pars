"""Вспомогательные утилиты."""

from __future__ import annotations

from datetime import datetime, timezone


def utcnow() -> datetime:
    """Текущее время в UTC (aware)."""
    return datetime.now(timezone.utc)


def ensure_aware(value: datetime) -> datetime:
    """Приводит naive datetime к UTC-aware (значения из SQLite бывают naive)."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def to_utc(value: datetime) -> datetime:
    return ensure_aware(value).astimezone(timezone.utc)
