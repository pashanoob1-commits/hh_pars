"""Тесты парсинга пользовательского ввода и форматирования."""

from __future__ import annotations

import pytest

from bot.handlers.parsing import format_stop_words, parse_positive_int, parse_stop_words
from bot.hh_api.models import HHVacancy, SalaryRange
from bot.services.formatter import (
    format_salary,
    format_vacancy_message,
    vacancy_to_payload,
)


def test_parse_positive_int():
    assert parse_positive_int("100000") == 100000
    assert parse_positive_int(" 100 000 ") == 100000
    assert parse_positive_int("-") is None
    assert parse_positive_int("пропустить") is None
    with pytest.raises(ValueError):
        parse_positive_int("много")


def test_parse_stop_words():
    assert parse_stop_words("1С, продажи; стажёр") == ["1с", "продажи", "стажёр"]
    assert parse_stop_words("Python\nDjango") == ["python", "django"]
    assert parse_stop_words("-") == []
    # дубликаты убираются
    assert parse_stop_words("qa, QA") == ["qa"]


def test_format_stop_words():
    assert format_stop_words(["1с"]) == "1с"
    assert format_stop_words([]) == "нет"


def test_format_salary_variants():
    assert format_salary(SalaryRange(from_amount=100000, to_amount=150000, currency="RUR")) == (
        "100 000 – 150 000 ₽"
    )
    assert format_salary(SalaryRange(from_amount=100000, currency="RUR")) == "от 100 000 ₽"
    assert format_salary(SalaryRange(to_amount=90000, currency="USD")) == "до 90 000 $"
    assert format_salary(SalaryRange(currency="RUR")) == "не указана"


def test_format_vacancy_message_escapes_html():
    vacancy = HHVacancy(
        id="1",
        name="Python <b>developer</b>",
        employer_name="ACME & Co",
        area_name="Москва",
        snippet_requirement="Python, Django",
        alternate_url="https://hh.ru/vacancy/1",
    )
    text = format_vacancy_message(
        vacancy, SalaryRange(from_amount=200000, currency="RUR"), subscription_title="«python» (Москва)"
    )
    assert "&lt;b&gt;developer&lt;/b&gt;" in text
    assert "ACME &amp; Co" in text
    assert "200 000 ₽" in text
    assert "Подписка" in text


def test_vacancy_to_payload():
    vacancy = HHVacancy(
        id="42",
        name="QA Engineer",
        employer_id="7",
        employer_name="QA Corp",
        area_name="СПб",
        alternate_url="https://hh.ru/vacancy/42",
        key_skills=["Selenium"],
    )
    payload = vacancy_to_payload(vacancy, SalaryRange(from_amount=1, to_amount=2, currency="RUR"))
    assert payload["vacancy_id"] == "42"
    assert payload["employer_id"] == "7"
    assert payload["currency"] == "RUR"
    assert payload["key_skills"] == ["Selenium"]
