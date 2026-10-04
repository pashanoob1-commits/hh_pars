"""Аналитика по подписке: медианная зарплата, топ навыков, динамика, CSV."""

from __future__ import annotations

import csv
import io
import statistics
from collections import Counter
from collections.abc import Iterable
from datetime import date, datetime
from typing import Any

from bot.db.models import SentVacancy


def _salary_midpoint(payload: dict[str, Any]) -> float | None:
    low = payload.get("salary_from")
    high = payload.get("salary_to")
    if low and high:
        return (float(low) + float(high)) / 2
    if low:
        return float(low)
    if high:
        return float(high)
    return None


def median_salary(records: Iterable[SentVacancy]) -> float | None:
    values = [
        value
        for value in (_salary_midpoint(record.payload or {}) for record in records)
        if value is not None
    ]
    return statistics.median(values) if values else None


def top_skills(records: Iterable[SentVacancy], limit: int = 10) -> list[tuple[str, int]]:
    counter: Counter[str] = Counter()
    for record in records:
        for skill in (record.payload or {}).get("key_skills", []) or []:
            if skill:
                counter[str(skill)] += 1
    return counter.most_common(limit)


def dynamics_by_day(records: Iterable[SentVacancy]) -> list[tuple[date, int]]:
    counter: Counter[date] = Counter()
    for record in records:
        moment: datetime | None = record.sent_at
        if moment is None:
            published = (record.payload or {}).get("published_at")
            moment = datetime.fromisoformat(published) if published else None
        if moment is not None:
            counter[moment.date()] += 1
    return sorted(counter.items())


def records_to_csv(records: Iterable[SentVacancy]) -> str:
    """Экспорт выборки вакансий в CSV-строку."""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "vacancy_id",
            "title",
            "employer",
            "salary_from",
            "salary_to",
            "currency",
            "area",
            "url",
            "published_at",
            "sent_at",
        ]
    )
    for record in records:
        payload = record.payload or {}
        writer.writerow(
            [
                record.vacancy_id,
                payload.get("title", ""),
                payload.get("employer_name", ""),
                payload.get("salary_from", ""),
                payload.get("salary_to", ""),
                payload.get("currency", ""),
                payload.get("area_name", ""),
                payload.get("url", ""),
                payload.get("published_at", ""),
                record.sent_at.isoformat() if record.sent_at else "",
            ]
        )
    return buffer.getvalue()
