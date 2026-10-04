"""Мастер создания подписки и управление подписками."""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import Settings
from bot.db import repositories as repo
from bot.hh_api.client import HHAPIError, HHClient
from bot.handlers import keyboards as kb
from bot.handlers.parsing import format_stop_words, parse_positive_int, parse_stop_words
from bot.handlers.states import AddSubscription
from bot.services.dictionaries import employment_label, experience_label
from bot.services.subscriptions import (
    SubscriptionError,
    SubscriptionLimitReached,
    SubscriptionService,
    describe_subscription,
)

logger = logging.getLogger(__name__)
router = Router(name="subscriptions")


async def _get_user_id(session: AsyncSession, message: Message) -> int:
    user = await repo.get_or_create_user(
        session, message.from_user.id, message.from_user.username
    )
    return user.id


# --- /add: мастер -----------------------------------------------------------
@router.message(Command("add"))
async def cmd_add(
    message: Message, state: FSMContext, session: AsyncSession, settings: Settings
) -> None:
    user_id = await _get_user_id(session, message)
    count = await repo.count_subscriptions(session, user_id)
    if count >= settings.max_subscriptions_per_user:
        await message.answer(
            f"Достигнут лимит подписок ({settings.max_subscriptions_per_user}).\n"
            "Удалите ненужные командой /list или /del &lt;id&gt;."
        )
        return

    await state.clear()
    await state.set_state(AddSubscription.query)
    await state.update_data(user_id=user_id)
    await message.answer(
        "➕ <b>Новая подписка</b>\n\n"
        "Шаг 1/8. Введите поисковый запрос (например: <code>python backend</code>).\n"
        "Отмена — /cancel."
    )


@router.message(AddSubscription.query)
async def wizard_query(message: Message, state: FSMContext) -> None:
    query = (message.text or "").strip()
    if len(query) < 2:
        await message.answer("Слишком короткий запрос. Введите хотя бы 2 символа.")
        return
    await state.update_data(query=query)
    await state.set_state(AddSubscription.area)
    await message.answer(
        "Шаг 2/8. Выберите регион поиска:", reply_markup=kb.popular_areas_keyboard()
    )


@router.callback_query(AddSubscription.area, F.data == f"{kb.WIZ}:areasearch")
async def wizard_area_search(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AddSubscription.area_search)
    await callback.message.answer("Введите название региона (например: Самара).")
    await callback.answer()


@router.message(AddSubscription.area_search)
async def wizard_area_search_result(
    message: Message, state: FSMContext, hh_client: HHClient
) -> None:
    query = (message.text or "").strip()
    try:
        areas = await hh_client.find_areas(query, limit=10)
    except HHAPIError as exc:
        logger.warning("Ошибка поиска регионов: %s", exc)
        await message.answer("Не удалось получить список регионов. Попробуйте ещё раз.")
        return

    if not areas:
        await message.answer(
            "Ничего не найдено. Попробуйте другое название или выберите из списка.",
            reply_markup=kb.popular_areas_keyboard(),
        )
        await state.set_state(AddSubscription.area)
        return

    await state.update_data(
        area_options={str(area.id): area.name for area in areas}
    )
    options = [(area.id, area.name) for area in areas]
    await message.answer(
        "Выберите регион:", reply_markup=kb.area_search_results_keyboard(options)
    )


@router.callback_query(AddSubscription.area, F.data.startswith(f"{kb.WIZ}:area:"))
async def wizard_area_picked(callback: CallbackQuery, state: FSMContext) -> None:
    _, _, area_id, area_name = callback.data.split(":", 3)
    await state.update_data(area_id=int(area_id), area_name=area_name)
    await state.set_state(AddSubscription.experience)
    await callback.message.answer(
        "Шаг 3/8. Требуемый опыт работы:", reply_markup=kb.experience_keyboard()
    )
    await callback.answer()


@router.callback_query(AddSubscription.experience, F.data.startswith(f"{kb.WIZ}:exp:"))
async def wizard_experience(callback: CallbackQuery, state: FSMContext) -> None:
    value = callback.data.rsplit(":", 1)[1]
    await state.update_data(experience=None if value == "skip" else value)
    await state.set_state(AddSubscription.employment)
    await callback.message.answer(
        "Шаг 4/8. Тип занятости:", reply_markup=kb.employment_keyboard()
    )
    await callback.answer()


@router.callback_query(AddSubscription.employment, F.data.startswith(f"{kb.WIZ}:emp:"))
async def wizard_employment(callback: CallbackQuery, state: FSMContext) -> None:
    value = callback.data.rsplit(":", 1)[1]
    await state.update_data(employment=None if value == "skip" else value)
    await state.set_state(AddSubscription.salary_min)
    await callback.message.answer(
        "Шаг 5/8. Минимальная зарплата, ₽ (число или «-», чтобы пропустить)."
    )
    await callback.answer()


@router.message(AddSubscription.salary_min)
async def wizard_salary_min(message: Message, state: FSMContext) -> None:
    try:
        value = parse_positive_int(message.text or "")
    except ValueError as exc:
        await message.answer(str(exc))
        return
    await state.update_data(salary_min=value)
    await state.set_state(AddSubscription.salary_max)
    await message.answer("Шаг 6/8. Максимальная зарплата, ₽ (число или «-»).")


@router.message(AddSubscription.salary_max)
async def wizard_salary_max(message: Message, state: FSMContext) -> None:
    try:
        value = parse_positive_int(message.text or "")
    except ValueError as exc:
        await message.answer(str(exc))
        return

    data = await state.get_data()
    salary_min = data.get("salary_min")
    if value is not None and salary_min is not None and value < salary_min:
        await message.answer("Максимум меньше минимума. Введите значение больше минимума.")
        return

    await state.update_data(salary_max=value)
    await state.set_state(AddSubscription.only_with_salary)
    await message.answer(
        "Шаг 7/8. Показывать только вакансии с указанной зарплатой?",
        reply_markup=kb.only_with_salary_keyboard(),
    )


@router.callback_query(AddSubscription.only_with_salary, F.data.startswith(f"{kb.WIZ}:ows:"))
async def wizard_only_with_salary(callback: CallbackQuery, state: FSMContext) -> None:
    value = callback.data.rsplit(":", 1)[1] == "yes"
    await state.update_data(only_with_salary=value)
    await state.set_state(AddSubscription.stop_words)
    await callback.message.answer(
        "Шаг 8/8. Стоп-слова — если слово встречается в названии или описании, "
        "вакансия не показывается.\n"
        "Введите слова через запятую (например: <code>1С, продажи, стажёр</code>) "
        "или «-», чтобы пропустить."
    )
    await callback.answer()


@router.message(AddSubscription.stop_words)
async def wizard_stop_words(message: Message, state: FSMContext) -> None:
    words = parse_stop_words(message.text or "")
    await state.update_data(stop_words=words)
    data = await state.get_data()
    await state.set_state(AddSubscription.confirm)

    preview = _format_preview(data)
    await message.answer(
        "Проверьте подписку:\n\n" + preview,
        reply_markup=kb.confirm_keyboard(),
    )


def _format_preview(data: dict) -> str:
    salary = "не задана"
    if data.get("salary_min") or data.get("salary_max"):
        salary = f"{data.get('salary_min') or '…'} – {data.get('salary_max') or '…'} ₽"
    lines = [
        f"🔎 Запрос: <b>{data.get('query')}</b>",
        f"📍 Регион: {data.get('area_name')}",
        f"🎓 Опыт: {experience_label(data.get('experience'))}",
        f"💼 Занятость: {employment_label(data.get('employment'))}",
        f"💰 Зарплата: {salary}",
        f"💵 Только с зарплатой: {'да' if data.get('only_with_salary') else 'нет'}",
        f"🚫 Стоп-слова: {format_stop_words(data.get('stop_words') or [])}",
    ]
    return "\n".join(lines)


@router.callback_query(AddSubscription.confirm, F.data == f"{kb.WIZ}:cancel")
async def wizard_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.answer("Создание подписки отменено.")
    await callback.answer()


@router.callback_query(AddSubscription.confirm, F.data == f"{kb.WIZ}:confirm")
async def wizard_confirm(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession, settings: Settings
) -> None:
    data = await state.get_data()
    service = SubscriptionService(session, settings)

    try:
        subscription = await service.create(
            data["user_id"],
            query=data["query"],
            area_id=data["area_id"],
            area_name=data["area_name"],
            experience=data.get("experience"),
            employment=data.get("employment"),
            salary_min=data.get("salary_min"),
            salary_max=data.get("salary_max"),
            only_with_salary=bool(data.get("only_with_salary")),
            stop_words=data.get("stop_words") or [],
        )
    except SubscriptionLimitReached as exc:
        await callback.message.answer(str(exc))
    except SubscriptionError as exc:
        await callback.message.answer(f"Не получилось: {exc}")
    else:
        await state.clear()
        await callback.message.answer(
            f"✅ Подписка #{subscription.id} создана.\n"
            f"{describe_subscription(subscription)}\n\n"
            f"Первые вакансии придут в течение "
            f"{settings.poll_interval_minutes} мин. Управление — /list."
        )
    await callback.answer()

# --- /list, /del, /pause, /resume -------------------------------------------
@router.message(Command("list"))
async def cmd_list(message: Message, session: AsyncSession, settings: Settings) -> None:
    user_id = await _get_user_id(session, message)
    subscriptions = await repo.list_subscriptions(session, user_id)

    if not subscriptions:
        await message.answer("Подписок пока нет. Создайте первую: /add")
        return

    await message.answer(
        f"📋 Ваши подписки ({len(subscriptions)}/{settings.max_subscriptions_per_user}):"
    )
    for sub in subscriptions:
        status = "🟢 активна" if sub.is_active else "⏸ на паузе"
        text = f"<b>#{sub.id}</b> · {status}\n{describe_subscription(sub)}"
        await message.answer(text, reply_markup=kb.subscription_manage_keyboard(sub))


def _parse_id(argument: str | None) -> int | None:
    """Достаёт id подписки из аргументов команды."""
    if not argument:
        return None
    first = argument.strip().split()[0]
    return int(first) if first.isdigit() else None


@router.message(Command("del"))
async def cmd_del(
    message: Message,
    session: AsyncSession,
    settings: Settings,
    command: CommandObject,
) -> None:
    user_id = await _get_user_id(session, message)
    subscription_id = _parse_id(command.args)

    if subscription_id is None:
        subscriptions = await repo.list_subscriptions(session, user_id)
        if not subscriptions:
            await message.answer("Подписок нет.")
            return
        await message.answer(
            "Выберите подписку для удаления:",
            reply_markup=kb.subscriptions_keyboard(subscriptions, "del"),
        )
        return

    service = SubscriptionService(session, settings)
    if await service.delete(user_id, subscription_id):
        await message.answer(f"🗑 Подписка #{subscription_id} удалена.")
    else:
        await message.answer("Подписка не найдена.")


@router.message(Command("pause"))
async def cmd_pause(message: Message, session: AsyncSession, settings: Settings, command: CommandObject) -> None:
    await _toggle(message, session, settings, command.args, active=False)


@router.message(Command("resume"))
async def cmd_resume(message: Message, session: AsyncSession, settings: Settings, command: CommandObject) -> None:
    await _toggle(message, session, settings, command.args, active=True)


async def _toggle(
    message: Message,
    session: AsyncSession,
    settings: Settings,
    argument: str | None,
    *,
    active: bool,
) -> None:
    user_id = await _get_user_id(session, message)
    subscription_id = _parse_id(argument)
    action = "resume" if active else "pause"

    if subscription_id is None:
        subscriptions = await repo.list_subscriptions(session, user_id)
        if not subscriptions:
            await message.answer("Подписок нет.")
            return
        await message.answer(
            "Выберите подписку:",
            reply_markup=kb.subscriptions_keyboard(subscriptions, action),
        )
        return

    service = SubscriptionService(session, settings)
    if await service.set_active(user_id, subscription_id, active):
        await message.answer(
            ("▶️ Подписка #%s возобновлена." % subscription_id)
            if active
            else ("⏸ Подписка #%s поставлена на паузу." % subscription_id)
        )
    else:
        await message.answer("Подписка не найдена.")


# --- Управление подпиской по кнопкам ----------------------------------------
@router.callback_query(F.data.startswith(f"{kb.SUB_ACTION}:del:"))
async def cb_delete(
    callback: CallbackQuery, session: AsyncSession, settings: Settings
) -> None:
    user_id = await _get_user_id(session, callback.message)
    subscription_id = int(callback.data.rsplit(":", 1)[1])
    if await SubscriptionService(session, settings).delete(user_id, subscription_id):
        await callback.message.edit_text(f"🗑 Подписка #{subscription_id} удалена.")
    else:
        await callback.answer("Подписка не найдена", show_alert=True)
        return
    await callback.answer()


@router.callback_query(F.data.startswith(f"{kb.SUB_ACTION}:pause:"))
async def cb_pause(
    callback: CallbackQuery, session: AsyncSession, settings: Settings
) -> None:
    await _cb_toggle(callback, session, settings, active=False)


@router.callback_query(F.data.startswith(f"{kb.SUB_ACTION}:resume:"))
async def cb_resume(
    callback: CallbackQuery, session: AsyncSession, settings: Settings
) -> None:
    await _cb_toggle(callback, session, settings, active=True)


async def _cb_toggle(
    callback: CallbackQuery, session: AsyncSession, settings: Settings, *, active: bool
) -> None:
    user_id = await _get_user_id(session, callback.message)
    subscription_id = int(callback.data.rsplit(":", 1)[1])
    service = SubscriptionService(session, settings)

    if not await service.set_active(user_id, subscription_id, active):
        await callback.answer("Подписка не найдена", show_alert=True)
        return

    subscription = await service.get(user_id, subscription_id)
    status = "🟢 активна" if active else "⏸ на паузе"
    await callback.message.edit_text(
        f"<b>#{subscription.id}</b> · {status}\n{describe_subscription(subscription)}",
        reply_markup=kb.subscription_manage_keyboard(subscription),
    )
    await callback.answer()

