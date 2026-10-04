"""Справочники значений для мастера подписок и отображения."""

from __future__ import annotations

# id API hh.ru -> человекочитаемая подпись
EXPERIENCE_OPTIONS: dict[str, str] = {
    "noExperience": "Нет опыта",
    "between1And3": "От 1 до 3 лет",
    "between3And6": "От 3 до 6 лет",
    "moreThan6": "Более 6 лет",
}

EMPLOYMENT_OPTIONS: dict[str, str] = {
    "full": "Полная занятость",
    "part": "Частичная занятость",
    "project": "Проектная работа",
    "probation": "Стажировка",
    "volunteer": "Волонтёрство",
}

# Популярные регионы для быстрых кнопок: id области hh.ru
POPULAR_AREAS: list[tuple[int, str]] = [
    (113, "🌍 Вся Россия"),
    (1, "Москва"),
    (2, "Санкт-Петербург"),
    (3, "Екатеринбург"),
    (4, "Новосибирск"),
    (88, "Казань"),
    (66, "Нижний Новгород"),
]

# Заранее известные подписи, чтобы не ходить в API
KNOWN_AREA_NAMES: dict[int, str] = {area_id: name for area_id, name in POPULAR_AREAS}


def experience_label(experience_id: str | None) -> str:
    if not experience_id:
        return "любой"
    return EXPERIENCE_OPTIONS.get(experience_id, experience_id)


def employment_label(employment_id: str | None) -> str:
    if not employment_id:
        return "любая"
    return EMPLOYMENT_OPTIONS.get(employment_id, employment_id)
