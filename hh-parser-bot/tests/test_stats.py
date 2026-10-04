"""Тесты аналитики: медиана, навыки, динамика, CSV."""

from __future__ import annotations

from datetime import datetime, timezone

from bot.services import stats
from bot.db.models import SentVacancy


def record(vacancy_id: str, payload: dict, sent_at: datetime | None = None) -> SentVacancy:
    item = SentVacancy(
        user_id=1, subscription_id=1, vacancy_id=vacancy_id, payload=payload
    )
    item.sent_at = sent_at or datetime(2024, 5, 1, 10, 0, tzinfo=timezone.utc)
    return item


def test_median_salary_uses_salary_midpoint():
    records = [
        record("1", {"salary_from": 100000, "salary_to": 200000}),
        record("2", {"salary_from": 300000}),
        record("3", {"salary_to": 400000}),
        record("4", {}),
    ]
    # 150k, 300k, 400k -> медиана 300k
    assert stats.median_salary(records) == 300000
    assert stats.median_salary([]) is None


def test_top_skills():
    records = [
        record("1", {"key_skills": ["Python", "SQL"]}),
        record("2", {"key_skills": ["Python", "Django"]}),
        record("3", {"key_skills": ["Python"]}),
    ]
    assert stats.top_skills(records, limit=2) == [("Python", 3), ("SQL", 1)]


def test_dynamics_by_day():
    records = [
        record("1", {}, datetime(2024, 5, 1, tzinfo=timezone.utc)),
        record("2", {}, datetime(2024, 5, 1, 3, tzinfo=timezone.utc)),
        record("3", {}, datetime(2024, 5, 2, tzinfo=timezone.utc)),
    ]
    result = stats.dynamics_by_day(records)
    assert [(day.isoformat(), count) for day, count in result] == [
        ("2024-05-01", 2),
        ("2024-05-02", 1),
    ]


def test_records_to_csv_contains_rows():
    records = [
        record(
            "1",
            {
                "title": "Python dev",
                "employer_name": "ACME",
                "salary_from": 100000,
                "salary_to": 150000,
                "currency": "RUR",
                "area_name": "Москва",
                "url": "https://hh.ru/vacancy/1",
            },
        )
    ]
    csv_text = stats.records_to_csv(records)
    lines = csv_text.strip().splitlines()
    assert lines[0].startswith("vacancy_id,title,employer")
    assert "Python dev" in lines[1]
    assert "100000" in lines[1]
