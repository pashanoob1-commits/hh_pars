"""Тесты фильтрации вакансий (стоп-слова, компании, вилка, свежесть)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from bot.hh_api.models import HHVacancy
from bot.services.filters import (
    apply_subscription_filters,
    filter_by_employers,
    filter_by_salary_max,
    filter_by_stop_words,
    filter_newer_than,
    is_stop_word_hit,
)


def vacancy(
    vacancy_id: str,
    *,
    name: str = "Python разработчик",
    employer_id: str = "1",
    salary_from: int | None = 100000,
    salary_to: int | None = 150000,
    requirement: str | None = "Python, FastAPI",
    published_at: datetime | None = None,
) -> HHVacancy:
    return HHVacancy(
        id=vacancy_id,
        name=name,
        employer_id=employer_id,
        employer_name=f"Company {employer_id}",
        salary_from=salary_from,
        salary_to=salary_to,
        snippet_requirement=requirement,
        published_at=published_at,
    )


def test_stop_word_matches_title_and_snippet():
    item = vacancy("1", name="Продавец-консультант", requirement="Работа с 1С")
    assert is_stop_word_hit(item, ["продавец"])
    assert is_stop_word_hit(item, ["1с"])
    assert not is_stop_word_hit(item, ["python"])


def test_stop_word_case_insensitive_and_empty():
    item = vacancy("1", name="Python Developer")
    assert is_stop_word_hit(item, ["PYTHON"])
    assert not is_stop_word_hit(item, [])
    assert not is_stop_word_hit(item, ["  "])


def test_filter_by_stop_words():
    items = [vacancy("1", name="Python dev"), vacancy("2", name="Продавец, python")]
    result = filter_by_stop_words(items, ["продавец"])
    assert [item.id for item in result] == ["1"]


def test_filter_by_employers():
    items = [vacancy("1", employer_id="10"), vacancy("2", employer_id="20")]
    result = filter_by_employers(items, {"20"})
    assert [item.id for item in result] == ["1"]
    assert filter_by_employers(items, set()) == items


def test_filter_by_salary_max_keeps_vacancies_without_salary():
    items = [
        vacancy("1", salary_from=100000, salary_to=120000),
        vacancy("2", salary_from=300000, salary_to=None),
        vacancy("3", salary_from=None, salary_to=None),
    ]
    result = filter_by_salary_max(items, 200000)
    assert [item.id for item in result] == ["1", "3"]


def test_filter_newer_than_watermark():
    now = datetime(2024, 5, 1, 12, 0, tzinfo=timezone.utc)
    old = vacancy("old", published_at=now - timedelta(hours=2))
    fresh = vacancy("new", published_at=now + timedelta(minutes=5))

    result = filter_newer_than([old, fresh], now)
    assert [item.id for item in result] == ["new"]
    # Без watermark пропускаем всё
    assert len(filter_newer_than([old, fresh], None)) == 2


def test_apply_subscription_filters_combined():
    now = datetime(2024, 5, 1, 12, 0, tzinfo=timezone.utc)
    items = [
        vacancy("keep", published_at=now + timedelta(minutes=1)),
        vacancy("stopword", name="Python, продажи", published_at=now + timedelta(minutes=1)),
        vacancy("blocked", employer_id="42", published_at=now + timedelta(minutes=1)),
        vacancy("old", published_at=now - timedelta(days=1)),
        vacancy(
            "too_expensive",
            salary_from=500000,
            salary_to=None,
            published_at=now + timedelta(minutes=1),
        ),
    ]

    result = apply_subscription_filters(
        items,
        stop_words=["продажи"],
        blocked_employer_ids={"42"},
        salary_max=200000,
        published_after=now,
    )
    assert [item.id for item in result] == ["keep"]
