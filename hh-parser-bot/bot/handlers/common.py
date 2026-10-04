"""Кнопки под уведомлениями: «в избранное» и «скрыть компанию»."""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db import repositories as repo
from bot.hh_api.client import HHAPIError, HHClient
from bot.services.notifier import CALLBACK_FAVORITE, CALLBACK_HIDE_EMPLOYER

logger = logging.getLogger(__name__)
router = Router(name="vacancy_actions")


async def _user_id(session: AsyncSession, callback: CallbackQuery) -> int:
    user = await repo.get_or_create_user(
        session, callback.from_user.id, callback.from_user.username
    )
    return user.id


async def _resolve_payload(
    session: AsyncSession, client: HHClient, user_id: int, vacancy_id: str
) -> dict | None:
    """Берёт снимок вакансии из истории отправки, при отсутствии — из API."""
    payload = await repo.get_sent_payload(session, user_id, vacancy_id)
    if payload:
        return payload

    raw = await client.get_vacancy(vacancy_id)
    if not raw:
        return None
    return {
        "vacancy_id": vacancy_id,
        "title": raw.get("name", ""),
        "employer_id": str((raw.get("employer") or {}).get("id") or "") or None,
        "employer_name": (raw.get("employer") or {}).get("name"),
        "area_name": (raw.get("area") or {}).get("name"),
        "url": raw.get("alternate_url", ""),
    }


@router.callback_query(F.data.startswith(f"{CALLBACK_FAVORITE}:"))
async def cb_favorite(
    callback: CallbackQuery, session: AsyncSession, hh_client: HHClient
) -> None:
    vacancy_id = callback.data.rsplit(":", 1)[1]
    user_id = await _user_id(session, callback)

    payload = await _resolve_payload(session, hh_client, user_id, vacancy_id)
    if payload is None:
        await callback.answer("Не удалось получить вакансию", show_alert=True)
        return

    await repo.add_favorite(session, user_id, payload)
    await callback.answer("⭐ Добавлено в избранное")


@router.callback_query(F.data.startswith(f"{CALLBACK_HIDE_EMPLOYER}:"))
async def cb_hide_employer(
    callback: CallbackQuery, session: AsyncSession, hh_client: HHClient
) -> None:
    vacancy_id = callback.data.rsplit(":", 1)[1]
    user_id = await _user_id(session, callback)

    try:
        payload = await _resolve_payload(session, hh_client, user_id, vacancy_id)
    except HHAPIError as exc:  # страховка: API может быть недоступен
        logger.warning("Не удалось скрыть компанию: %s", exc)
        payload = None

    if not payload or not payload.get("employer_id"):
        await callback.answer("Не удалось определить компанию", show_alert=True)
        return

    employer_name = payload.get("employer_name") or "Без названия"
    await repo.add_blocked_employer(
        session, user_id, str(payload["employer_id"]), employer_name
    )

    try:
        await callback.message.edit_text(
            (callback.message.html_text or callback.message.text or "")
            + f"\n\n🚫 Компания «{employer_name}» скрыта.",
            reply_markup=None,
        )
    except Exception:  # noqa: BLE001 — правка сообщения не критична
        pass

    await callback.answer("🚫 Компания скрыта")
