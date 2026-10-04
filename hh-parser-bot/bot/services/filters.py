"""Фильтрация вакансий: стоп-слова, чёрный список, вилка, свежесть."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import datetime

from bot.hh_api.models import HHVacancy
from bot.utils.time import to_utc


def is_stop_word_hit(vacancy: HHVacancy, stop_words: Sequence[str]) -> bool:
    """True, если в названии/описании вакансии встречается стоп-слово."""
    if not stop_words:
        return False
    text = vacancy.searchable_text
    return any(word.strip().lower() in text for word in stop_words if word.strip())


def filter_by_stop_words(
    vacancies: Iterable[HHVacancy], stop_words: Sequence[str]
) -> list[HHVacancy]:
    return [v for v in vacancies if not is_stop_word_hit(v, stop_words)]


def filter_by_employers(
    vacancies: Iterable[HHVacancy], blocked_employer_ids: set[str]
) -> list[HHVacancy]:
    if not blocked_employer_ids:
        return list(vacancies)
    return [v for v in vacancies if (v.employer_id or "") not in blocked_employer_ids]


def filter_by_salary_max(
    vacancies: Iterable[HHVacancy], salary_max: int | None
) -> list[HHVacancy]:
    """Верхняя граница вилки: API hh поддерживает только salary (минимум),
    поэтому максимальную зарплату отсекаем сами.

    Вакансии без указанной зарплаты не отбрасываем — иначе потеряем много вариантов.
    """
    if salary_max is None:
        return list(vacancies)

    result: list[HHVacancy] = []
    for vacancy in vacancies:
        lower_bound = vacancy.salary_from or vacancy.salary_to
        if lower_bound is None or lower_bound <= salary_max:
            result.append(vacancy)
    return result


def filter_newer_than(
    vacancies: Iterable[HHVacancy], moment: datetime | None
) -> list[HHVacancy]:
    """Оставляет вакансии, опубликованные позже moment (watermark подписки)."""
    if moment is None:
        return list(vacancies)
    threshold = to_utc(moment)
    result: list[HHVacancy] = []
    for vacancy in vacancies:
        if vacancy.published_at is None or to_utc(vacancy.published_at) > threshold:
            result.append(vacancy)
    return result


def apply_subscription_filters(
    vacancies: Iterable[HHVacancy],
    *,
    stop_words: Sequence[str] = (),
    blocked_employer_ids: set[str] | None = None,
    salary_max: int | None = None,
    published_after: datetime | None = None,
) -> list[HHVacancy]:
    """Применяет все фильтры подписки в один проход."""
    result = list(vacancies)
    result = filter_by_stop_words(result, stop_words)
    result = filter_by_employers(result, blocked_employer_ids or set())
    result = filter_by_salary_max(result, salary_max)
    result = filter_newer_than(result, published_after)
    return result
