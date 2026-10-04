"""Inline-клавиатуры бота."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.db.models import Subscription
from bot.services.dictionaries import (
    EMPLOYMENT_OPTIONS,
    EXPERIENCE_OPTIONS,
    POPULAR_AREAS,
    experience_label,
    employment_label,
)

# Префиксы callback_data
WIZ = "wiz"
SUB_ACTION = "sub"


def popular_areas_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=name, callback_data=f"{WIZ}:area:{area_id}:{name}")]
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
        [InlineKeyboardButton(text=name, callback_data=f"{WIZ}:area:{area_id}:{name}")]
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
    rows = [
        [
            InlineKeyboardButton(
                text=f"#{sub.id} {sub.query[:30]} ({sub.area_name})",
                callback_data=f"{SUB_ACTION}:{action}:{sub.id}",
            )
        ]
        for sub in subs
    ]
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
    rows = [
        [
            InlineKeyboardButton(
                text=f"❌ {name}", callback_data=f"{SUB_ACTION}:unblock:{blocker_id}"
            )
        ]
        for blocker_id, name in blockers
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


__all__ = [
    "popular_areas_keyboard",
    "area_search_results_keyboard",
    "experience_keyboard",
    "employment_keyboard",
    "only_with_salary_keyboard",
    "confirm_keyboard",
    "subscriptions_keyboard",
    "subscription_manage_keyboard",
    "blocked_employers_keyboard",
    "experience_label",
    "employment_label",
    "WIZ",
    "SUB_ACTION",
]
