"""Команды /start и /help."""

from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import Settings
from bot.db import repositories as repo

router = Router(name="start")

HELP_TEXT = (
    "🤖 <b>hh-parser-bot</b> — мониторинг вакансий hh.ru через официальный API.\n\n"
    "<b>Команды</b>\n"
    "/add — создать подписку на поиск вакансий\n"
    "/list — мои подписки (с кнопками управления)\n"
    "/del &lt;id&gt; — удалить подписку\n"
    "/pause &lt;id&gt; — поставить на паузу\n"
    "/resume &lt;id&gt; — возобновить\n"
    "/stopwords &lt;id&gt; — стоп-слова подписки\n"
    "/favorites — избранные вакансии\n"
    "/unblock — чёрный список компаний\n"
    "/stats &lt;id&gt; — статистика по подписке\n"
    "/cancel — отменить текущий диалог\n"
    "/help — эта справка\n\n"
    "Вакансии приходят автоматически: только новые, без повторов."
)


@router.message(Command("start"))
async def cmd_start(
    message: Message,
    session: AsyncSession,
    settings: Settings,
    command: CommandObject | None = None,
) -> None:
    user = await repo.get_or_create_user(
        session,
        telegram_id=message.from_user.id,
        username=message.from_user.username,
    )
    await message.answer(
        "Привет, {name}! 👋\n\n"
        "Я слежу за новыми вакансиями на hh.ru и присылаю их по вашим подпискам.\n"
        "Интервал проверки: каждые {minutes} мин. Лимит подписок: {limit}.\n\n"
        "Начните с команды /add — создам первую подписку.\n"
        "Полный список команд — /help.".format(
            name=message.from_user.full_name,
            minutes=settings.poll_interval_minutes,
            limit=settings.max_subscriptions_per_user,
        )
    )


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(HELP_TEXT)


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    current = await state.get_state()
    if current is None:
        await message.answer("Нечего отменять.")
        return
    await state.clear()
    await message.answer("Диалог отменён. Команды — /help.")
