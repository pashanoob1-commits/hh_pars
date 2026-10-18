"""Inline-клавиатуры бота."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.db.models import Subscription
from bot.services.dictionaries import (
    EMPLOYMENT_OPTIONS,
    EXPERIENCE_OPTIONS,
    POPULAR_AREAS,
    employment_label,
    experience_label,
)

# Префиксы callback_data
WIZ = "wiz"
SUB_ACTION = "sub"


def popular_areas_keyboard() -> InlineKeyboardMarkup:
    # В callback_data кладём только id: название региона может не влезть в лимит
    # Telegram в 64 байта (например, длинные названия из /areas).
    rows = [
        [InlineKeyboardButton(text=name, callback_data=f"{WIZ}:area:{area_id}")]
        for area_id, name in POPULAR_AREAS
    ]
    rows.append(
        [
            InlineKeyboardButton(
                text="🔍 Найти другой регион", callback_data=f"{WIZ}:areasearch"
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def area_search_results_keyboard(areas: list[tuple[int, str]]) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=name, callback_data=f"{WIZ}:area:{area_id}")]
        for area_id, name in areas
    ]
    rows.append(
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"{WIZ}:areasearch")]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def experience_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=label, callback_data=f"{WIZ}:exp:{value}")]
        for value, label in EXPERIENCE_OPTIONS.items()
    ]
    rows.append([InlineKeyboardButton(text="Любой опыт", callback_data=f"{WIZ}:exp:skip")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def employment_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=label, callback_data=f"{WIZ}:emp:{value}")]
        for value, label in EMPLOYMENT_OPTIONS.items()
    ]
    rows.append([InlineKeyboardButton(text="Любая занятость", callback_data=f"{WIZ}:emp:skip")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def only_with_salary_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Да, только с зарплатой", callback_data=f"{WIZ}:ows:yes"),
                InlineKeyboardButton(text="Нет, любые", callback_data=f"{WIZ}:ows:no"),
            ]
        ]
    )


def confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Создать", callback_data=f"{WIZ}:confirm"),
                InlineKeyboardButton(text="❌ Отмена", callback_data=f"{WIZ}:cancel"),
            ]
        ]
    )


def subscriptions_keyboard(subs: list[Subscription], action: str) -> InlineKeyboardMarkup:
    """Клавиатура выбора подписки для /del, /pause, /resume, /stats, /stopwords."""
    rows = []
    for sub in subs:
        label = f"#{sub.id} {sub.query[:30]} ({sub.area_name})"
        # Telegram ограничивает текст кнопки 64 символами.
        if len(label) > 60:
            label = label[:59] + "…"
        rows.append(
            [
                InlineKeyboardButton(
                    text=label,
                    callback_data=f"{SUB_ACTION}:{action}:{sub.id}",
                )
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def subscription_manage_keyboard(subscription: Subscription) -> InlineKeyboardMarkup:
    toggle_label = "▶️ Возобновить" if not subscription.is_active else "⏸ Пауза"
    toggle_action = "resume" if not subscription.is_active else "pause"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=toggle_label,
                    callback_data=f"{SUB_ACTION}:{toggle_action}:{subscription.id}",
                ),
                InlineKeyboardButton(
                    text="🗑 Удалить",
                    callback_data=f"{SUB_ACTION}:del:{subscription.id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🚫 Стоп-слова",
                    callback_data=f"{SUB_ACTION}:stopwords:{subscription.id}",
                ),
                InlineKeyboardButton(
                    text="📊 Статистика",
                    callback_data=f"{SUB_ACTION}:stats:{subscription.id}",
                ),
            ],
        ]
    )


def blocked_employers_keyboard(blockers: list[tuple[int, str]]) -> InlineKeyboardMarkup:
    rows = []
    for blocker_id, name in blockers:
        label = f"❌ {name}"
        if len(label) > 60:
            label = label[:59] + "…"
        rows.append(
            [
                InlineKeyboardButton(
                    text=label, callback_data=f"{SUB_ACTION}:unblock:{blocker_id}"
                )
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


FAVORITE_ACTION = "favdel"


def favorite_item_keyboard(vacancy_id: str) -> InlineKeyboardMarkup:
    """Кнопка удаления вакансии из избранного."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🗑 Убрать из избранного",
                    callback_data=f"{FAVORITE_ACTION}:{vacancy_id}",
                )
            ]
        ]
    )


__all__ = [
    "FAVORITE_ACTION",
    "SUB_ACTION",
    "WIZ",
    "area_search_results_keyboard",
    "blocked_employers_keyboard",
    "confirm_keyboard",
    "employment_keyboard",
    "employment_label",
    "experience_keyboard",
    "experience_label",
    "favorite_item_keyboard",
    "only_with_salary_keyboard",
    "popular_areas_keyboard",
    "subscription_manage_keyboard",
    "subscriptions_keyboard",
]
