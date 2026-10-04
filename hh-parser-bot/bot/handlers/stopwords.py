"""Управление стоп-словами подписки (/stopwords)."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import Settings
from bot.db import repositories as repo
from bot.handlers.parsing import format_stop_words, parse_stop_words
from bot.handlers.states import StopWordsFlow
from bot.services.subscriptions import SubscriptionService

router = Router(name="stopwords")

SW = "sw"


def _words_keyboard(subscription_id: int, words: list[str]) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=f"➖ {word}", callback_data=f"{SW}:rm:{subscription_id}:{index}"
            )
        ]
        for index, word in enumerate(words)
    ]
    rows.append(
        [
            InlineKeyboardButton(
                text="➕ Добавить слова", callback_data=f"{SW}:add:{subscription_id}"
            ),
            InlineKeyboardButton(
                text="🧹 Очистить", callback_data=f"{SW}:clear:{subscription_id}"
            ),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _render(subscription_id: int, words: list[str]) -> str:
    return (
        f"🚫 <b>Стоп-слова подписки #{subscription_id}</b>\n"
        "Вакансии, в названии или описании которых встречается хотя бы одно слово, "
        "не показываются.\n\n"
        f"Сейчас: {format_stop_words(words)}"
    )


async def _get_user_id(session: AsyncSession, message: Message) -> int:
    user = await repo.get_or_create_user(
        session, message.from_user.id, message.from_user.username
    )
    return user.id


@router.message(Command("stopwords"))
async def cmd_stopwords(
    message: Message, session: AsyncSession, settings: Settings, command: CommandObject
) -> None:
    user_id = await _get_user_id(session, message)
    args = (command.args or "").strip()

    if not args:
        subscriptions = await repo.list_subscriptions(session, user_id)
        if not subscriptions:
            await message.answer("Подписок нет. Создайте первую: /add")
            return
        from bot.handlers import keyboards as kb

        await message.answer(
            "Выберите подписку, чтобы настроить стоп-слова:",
            reply_markup=kb.subscriptions_keyboard(subscriptions, "stopwords"),
        )
        return

    parts = args.split(maxsplit=1)
    if not parts[0].isdigit():
        await message.answer("Формат: /stopwords &lt;id&gt; [add|del|clear] [слова]")
        return

    subscription_id = int(parts[0])
    service = SubscriptionService(session, settings)
    subscription = await service.get(user_id, subscription_id)
    if subscription is None:
        await message.answer(f"Подписка #{subscription_id} не найдена.")
        return

    words = list(subscription.stop_words or [])
    rest = parts[1].strip() if len(parts) > 1 else ""

    if not rest:
        await message.answer(
            _render(subscription_id, words),
            reply_markup=_words_keyboard(subscription_id, words),
        )
        return

    action, _, payload = rest.partition(" ")
    action = action.lower()

    if action in {"add", "del", "clear"}:
        if action == "clear":
            words = []
        else:
            incoming = parse_stop_words(payload)
            if not incoming:
                await message.answer("Не вижу слов. Пример: /stopwords 1 add 1С, продажи")
                return
            if action == "add":
                words.extend(word for word in incoming if word not in words)
            else:
                words = [word for word in words if word not in incoming]
        await service.set_stop_words(user_id, subscription_id, words)
        await message.answer(_render(subscription_id, words))
        return

    # Иначе считаем, что передан просто список слов (замена целиком).
    words = parse_stop_words(args.split(" ", 1)[1])
    await service.set_stop_words(user_id, subscription_id, words)
    await message.answer(_render(subscription_id, words))


@router.callback_query(F.data.startswith(f"{SW}:add:"))
async def cb_add_words(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession, settings: Settings
) -> None:
    user_id = await _get_user_id(session, callback.message)
    subscription_id = int(callback.data.rsplit(":", 1)[1])
    service = SubscriptionService(session, settings)
    if await service.get(user_id, subscription_id) is None:
        await callback.answer("Подписка не найдена", show_alert=True)
        return

    await state.set_state(StopWordsFlow.waiting_words)
    await state.update_data(subscription_id=subscription_id)
    await callback.message.answer(
        "Введите стоп-слова через запятую (например: <code>1С, продажи, стажёр</code>).\n"
        "Отмена — /cancel."
    )
    await callback.answer()


@router.message(StopWordsFlow.waiting_words)
async def wizard_words(
    message: Message, state: FSMContext, session: AsyncSession, settings: Settings
) -> None:
    data = await state.get_data()
    subscription_id = data.get("subscription_id")
    user_id = await _get_user_id(session, message)

    service = SubscriptionService(session, settings)
    subscription = await service.get(user_id, subscription_id)
    if subscription is None:
        await state.clear()
        await message.answer("Подписка не найдена.")
        return

    words = list(subscription.stop_words or [])
    words.extend(word for word in parse_stop_words(message.text or "") if word not in words)
    await service.set_stop_words(user_id, subscription_id, words)
    await state.clear()
    await message.answer(
        _render(subscription_id, words),
        reply_markup=_words_keyboard(subscription_id, words),
    )


@router.callback_query(F.data.startswith(f"{SW}:rm:"))
async def cb_remove_word(
    callback: CallbackQuery, session: AsyncSession, settings: Settings
) -> None:
    _, _, subscription_id_raw, index_raw = callback.data.split(":")
    subscription_id, index = int(subscription_id_raw), int(index_raw)
    user_id = await _get_user_id(session, callback.message)

    service = SubscriptionService(session, settings)
    subscription = await service.get(user_id, subscription_id)
    if subscription is None:
        await callback.answer("Подписка не найдена", show_alert=True)
        return

    words = list(subscription.stop_words or [])
    if 0 <= index < len(words):
        words.pop(index)
        await service.set_stop_words(user_id, subscription_id, words)

    await callback.message.edit_text(
        _render(subscription_id, words),
        reply_markup=_words_keyboard(subscription_id, words),
    )
    await callback.answer("Удалено")


@router.callback_query(F.data.startswith(f"{SW}:clear:"))
async def cb_clear_words(
    callback: CallbackQuery, session: AsyncSession, settings: Settings
) -> None:
    subscription_id = int(callback.data.rsplit(":", 1)[1])
    user_id = await _get_user_id(session, callback.message)
    service = SubscriptionService(session, settings)
    if await service.get(user_id, subscription_id) is None:
        await callback.answer("Подписка не найдена", show_alert=True)
        return

    await service.set_stop_words(user_id, subscription_id, [])
    await callback.message.edit_text(
        _render(subscription_id, []), reply_markup=_words_keyboard(subscription_id, [])
    )
    await callback.answer("Очищено")


@router.callback_query(F.data.startswith("sub:stopwords:"))
async def cb_open_stopwords(
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

    words = list(subscription.stop_words or [])
    await callback.message.answer(
        _render(subscription_id, words),
        reply_markup=_words_keyboard(subscription_id, words),
    )
    await callback.answer()
