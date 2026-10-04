"""Избранные вакансии и чёрный список компаний."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db import repositories as repo
from bot.handlers import keyboards as kb
from bot.services.formatter import CURRENCY_SIGNS, format_amount

router = Router(name="favorites")


async def _get_user_id(session: AsyncSession, message: Message) -> int:
    user = await repo.get_or_create_user(
        session, message.from_user.id, message.from_user.username
    )
    return user.id


@router.message(Command("favorites"))
async def cmd_favorites(message: Message, session: AsyncSession) -> None:
    user_id = await _get_user_id(session, message)
    favorites = await repo.list_favorites(session, user_id)

    if not favorites:
        await message.answer(
            "Избранных вакансий нет. Нажмите «⭐ В избранное» под уведомлением."
        )
        return

    await message.answer(f"⭐ Избранное ({len(favorites)}):")
    for item in favorites:
        sign = CURRENCY_SIGNS.get((item.currency or "RUR").upper(), item.currency or "")
        salary = "зарплата не указана"
        if item.salary_from or item.salary_to:
            low = format_amount(item.salary_from) if item.salary_from else "…"
            high = format_amount(item.salary_to) if item.salary_to else "…"
            salary = f"{low} – {high} {sign}"
        text = (
            f"<b>{item.title}</b>\n"
            f"🏢 {item.employer_name or '—'}\n"
            f"💰 {salary}\n"
            f"📍 {item.area_name or '—'}\n"
            f"{item.url}"
        )
        await message.answer(text, disable_web_page_preview=True)


@router.message(Command("unblock"))
async def cmd_unblock(
    message: Message, session: AsyncSession, command: CommandObject
) -> None:
    user_id = await _get_user_id(session, message)
    blockers = await repo.list_blocked_employers(session, user_id)

    if not blockers:
        await message.answer("Чёрный список пуст.")
        return

    arg = (command.args or "").strip()
    if arg.isdigit():
        if await repo.remove_blocked_employer(session, user_id, int(arg)):
            await message.answer(f"Компания разблокирована (#{arg}).")
        else:
            await message.answer("Запись не найдена.")
        return

    options = [(item.id, item.employer_name or item.employer_id) for item in blockers]
    await message.answer(
        "🚫 <b>Чёрный список</b> — нажмите, чтобы разблокировать:",
        reply_markup=kb.blocked_employers_keyboard(options),
    )


@router.callback_query(F.data.startswith(f"{kb.SUB_ACTION}:unblock:"))
async def cb_unblock(callback: CallbackQuery, session: AsyncSession) -> None:
    user_id = await _get_user_id(session, callback.message)
    blocker_id = int(callback.data.rsplit(":", 1)[1])

    if await repo.remove_blocked_employer(session, user_id, blocker_id):
        blockers = await repo.list_blocked_employers(session, user_id)
        options = [(item.id, item.employer_name or item.employer_id) for item in blockers]
        if options:
            await callback.message.edit_text(
                "🚫 <b>Чёрный список</b> — нажмите, чтобы разблокировать:",
                reply_markup=kb.blocked_employers_keyboard(options),
            )
        else:
            await callback.message.edit_text("Чёрный список пуст.")
        await callback.answer("Разблокировано")
    else:
        await callback.answer("Запись не найдена", show_alert=True)
