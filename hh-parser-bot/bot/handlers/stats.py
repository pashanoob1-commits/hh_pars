"""Статистика по подписке и экспорт выборки в CSV."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import Settings
from bot.db import repositories as repo
from bot.handlers import keyboards as kb
from bot.services import stats as stats_service
from bot.services.formatter import format_amount
from bot.services.subscriptions import SubscriptionService, describe_subscription

router = Router(name="stats")


async def _get_user_id(session: AsyncSession, message: Message) -> int:
    user = await repo.get_or_create_user(
        session, message.from_user.id, message.from_user.username
    )
    return user.id


def _render_stats(subscription, records) -> str:
    lines = [
        f"📊 <b>Статистика подписки #{subscription.id}</b>",
        describe_subscription(subscription),
        "",
        f"Отправлено вакансий: <b>{len(records)}</b>",
    ]

    median = stats_service.median_salary(records)
    if median is not None:
        lines.append(f"💰 Медианная зарплата: <b>{format_amount(int(median))}</b>")

    skills = stats_service.top_skills(records, limit=10)
    if skills:
        lines.append("")
        lines.append("<b>Топ навыков:</b>")
        for skill, count in skills:
            lines.append(f"• {skill} — {count}")

    dynamics = stats_service.dynamics_by_day(records)
    if dynamics:
        lines.append("")
        lines.append("<b>По дням:</b>")
        for day, count in dynamics[-7:]:
            lines.append(f"• {day.isoformat()}: {count}")

    return "\n".join(lines)


def _stats_keyboard(subscription_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📥 Экспорт в CSV",
                    callback_data=f"stats:csv:{subscription_id}",
                )
            ]
        ]
    )


@router.message(Command("stats"))
async def cmd_stats(
    message: Message, session: AsyncSession, settings: Settings, command: CommandObject
) -> None:
    user_id = await _get_user_id(session, message)
    arg = (command.args or "").strip()

    if not arg.isdigit():
        subscriptions = await repo.list_subscriptions(session, user_id)
        if not subscriptions:
            await message.answer("Подписок нет. Создайте первую: /add")
            return
        await message.answer(
            "Выберите подписку для статистики:",
            reply_markup=kb.subscriptions_keyboard(subscriptions, "stats"),
        )
        return

    subscription_id = int(arg)
    service = SubscriptionService(session, settings)
    subscription = await service.get(user_id, subscription_id)
    if subscription is None:
        await message.answer(f"Подписка #{subscription_id} не найдена.")
        return

    records = await repo.list_sent_for_subscription(session, user_id, subscription_id)
    await message.answer(
        _render_stats(subscription, records),
        reply_markup=_stats_keyboard(subscription_id),
    )


@router.callback_query(F.data.startswith(f"{kb.SUB_ACTION}:stats:"))
async def cb_stats(
    callback: CallbackQuery, session: AsyncSession, settings: Settings
) -> None:
    subscription_id = int(callback.data.rsplit(":", 1)[1])
    user_id = await _get_user_id(session, callback.message)
    subscription = await SubscriptionService(session, settings).get(
        user_id, subscription_id
    )
    if subscription is None:
        await callback.answer("Подписка не найдена", show_alert=True)
        return

    records = await repo.list_sent_for_subscription(session, user_id, subscription_id)
    await callback.message.answer(
        _render_stats(subscription, records),
        reply_markup=_stats_keyboard(subscription_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("stats:csv:"))
async def cb_export_csv(
    callback: CallbackQuery, session: AsyncSession, settings: Settings
) -> None:
    subscription_id = int(callback.data.rsplit(":", 1)[1])
    user_id = await _get_user_id(session, callback.message)
    service = SubscriptionService(session, settings)
    subscription = await service.get(user_id, subscription_id)
    if subscription is None:
        await callback.answer("Подписка не найдена", show_alert=True)
        return

    records = await repo.list_sent_for_subscription(session, user_id, subscription_id)
    if not records:
        await callback.answer("Пока нечего экспортировать", show_alert=True)
        return

    content = stats_service.records_to_csv(records).encode("utf-8-sig")
    document = BufferedInputFile(
        content, filename=f"subscription_{subscription_id}.csv"
    )
    await callback.message.answer_document(document, caption="📥 Экспорт выборки")
    await callback.answer()
