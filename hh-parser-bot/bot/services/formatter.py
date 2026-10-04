"""Форматирование вакансий для Telegram и сборка payload для БД/кнопок."""

from __future__ import annotations

from html import escape
from typing import Any

from bot.hh_api.models import HHVacancy, SalaryRange

CURRENCY_SIGNS: dict[str, str] = {
    "RUR": "₽",
    "RUB": "₽",
    "USD": "$",
    "EUR": "€",
    "KZT": "₸",
    "BYN": "Br",
    "UAH": "₴",
    "GEL": "₾",
    "UZS": "so'm",
    "AZN": "₼",
}


def format_amount(amount: int) -> str:
    return f"{amount:,}".replace(",", " ")


def format_salary(salary: SalaryRange) -> str:
    """Человекочитаемая зарплата в целевой валюте."""
    sign = CURRENCY_SIGNS.get(salary.currency.upper(), salary.currency)
    if salary.from_amount and salary.to_amount:
        return f"{format_amount(salary.from_amount)} – {format_amount(salary.to_amount)} {sign}"
    if salary.from_amount:
        return f"от {format_amount(salary.from_amount)} {sign}"
    if salary.to_amount:
        return f"до {format_amount(salary.to_amount)} {sign}"
    return "не указана"


def vacancy_to_payload(vacancy: HHVacancy, salary: SalaryRange) -> dict[str, Any]:
    """Снимок вакансии для sent_vacancies / favorite_vacancies."""
    return {
        "vacancy_id": vacancy.id,
        "title": vacancy.name,
        "employer_id": vacancy.employer_id,
        "employer_name": vacancy.employer_name,
        "salary_from": salary.from_amount,
        "salary_to": salary.to_amount,
        "currency": salary.currency,
        "area_name": vacancy.area_name,
        "url": vacancy.alternate_url,
        "published_at": vacancy.published_at.isoformat() if vacancy.published_at else None,
        "key_skills": vacancy.key_skills,
        "employment": vacancy.employment,
        "experience": vacancy.experience,
    }


def format_vacancy_message(
    vacancy: HHVacancy,
    salary: SalaryRange,
    *,
    subscription_title: str | None = None,
) -> str:
    """HTML-сообщение для уведомления о новой вакансии."""
    lines: list[str] = [f"<b>{escape(vacancy.name)}</b>"]

    if vacancy.employer_name:
        lines.append(f"🏢 {escape(vacancy.employer_name)}")
    lines.append(f"💰 {format_salary(salary)}")
    if vacancy.area_name:
        lines.append(f"📍 {escape(vacancy.area_name)}")
    if vacancy.experience:
        lines.append(f"🎓 Опыт: {escape(vacancy.experience)}")

    snippet = vacancy.snippet_requirement or vacancy.snippet_responsibility
    if snippet:
        text = snippet.strip()
        if len(text) > 300:
            text = text[:297].rstrip() + "..."
        lines.append("")
        lines.append(f"<i>{escape(text)}</i>")

    if subscription_title:
        lines.append("")
        lines.append(f"🔔 Подписка: {escape(subscription_title)}")

    return "\n".join(lines)
