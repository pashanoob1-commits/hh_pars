"""Репозитории: доступ к данным (никакой бизнес-логики)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Sequence

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import (
    BlockedEmployer,
    CurrencyRate,
    FavoriteVacancy,
    SentVacancy,
    Subscription,
    User,
)


# --- Пользователи ---------------------------------------------------------
async def get_or_create_user(
    session: AsyncSession, telegram_id: int, username: str | None = None
) -> User:
    user = await session.scalar(select(User).where(User.telegram_id == telegram_id))
    if user is None:
        user = User(telegram_id=telegram_id, username=username)
        session.add(user)
        await session.flush()
    elif username and user.username != username:
        user.username = username
    return user


async def get_user_by_telegram_id(session: AsyncSession, telegram_id: int) -> User | None:
    return await session.scalar(select(User).where(User.telegram_id == telegram_id))


# --- Подписки --------------------------------------------------------------
async def count_subscriptions(session: AsyncSession, user_id: int) -> int:
    count = await session.scalar(
        select(func.count(Subscription.id)).where(Subscription.user_id == user_id)
    )
    return int(count or 0)


async def create_subscription(
    session: AsyncSession,
    user_id: int,
    *,
    query: str,
    area_id: int,
    area_name: str,
    experience: str | None = None,
    employment: str | None = None,
    salary_min: int | None = None,
    salary_max: int | None = None,
    only_with_salary: bool = False,
    stop_words: Sequence[str] | None = None,
) -> Subscription:
    subscription = Subscription(
        user_id=user_id,
        query=query,
        area_id=area_id,
        area_name=area_name,
        experience=experience,
        employment=employment,
        salary_min=salary_min,
        salary_max=salary_max,
        only_with_salary=only_with_salary,
        stop_words=list(stop_words or []),
        is_active=True,
        last_checked_at=None,
    )
    session.add(subscription)
    await session.flush()
    return subscription


async def list_subscriptions(session: AsyncSession, user_id: int) -> list[Subscription]:
    result = await session.scalars(
        select(Subscription)
        .where(Subscription.user_id == user_id)
        .order_by(Subscription.id)
    )
    return list(result)


async def get_subscription(
    session: AsyncSession, user_id: int, subscription_id: int
) -> Subscription | None:
    return await session.scalar(
        select(Subscription).where(
            Subscription.id == subscription_id, Subscription.user_id == user_id
        )
    )


async def delete_subscription(session: AsyncSession, subscription: Subscription) -> None:
    await session.delete(subscription)


async def list_active_subscriptions(session: AsyncSession) -> list[Subscription]:
    """Все активные подписки — вход планировщика."""
    result = await session.scalars(
        select(Subscription)
        .where(Subscription.is_active.is_(True))
        .order_by(Subscription.id)
    )
    return list(result)


async def update_last_checked(
    session: AsyncSession, subscription: Subscription, moment: datetime
) -> None:
    subscription.last_checked_at = moment


async def update_stop_words(
    session: AsyncSession, subscription: Subscription, stop_words: Sequence[str]
) -> None:
    subscription.stop_words = list(stop_words)


# --- Отправленные вакансии (дедупликация) ---------------------------------
async def get_sent_vacancy_ids(
    session: AsyncSession, user_id: int, vacancy_ids: Sequence[str]
) -> set[str]:
    """Возвращает подмножество vacancy_ids, уже отправленных пользователю."""
    if not vacancy_ids:
        return set()
    result = await session.scalars(
        select(SentVacancy.vacancy_id).where(
            SentVacancy.user_id == user_id,
            SentVacancy.vacancy_id.in_(list(vacancy_ids)),
        )
    )
    return set(result)


async def mark_sent(
    session: AsyncSession,
    *,
    user_id: int,
    subscription_id: int,
    vacancy_id: str,
    payload: dict[str, Any] | None = None,
) -> None:
    session.add(
        SentVacancy(
            user_id=user_id,
            subscription_id=subscription_id,
            vacancy_id=vacancy_id,
            payload=payload or {},
        )
    )


async def get_sent_payload(
    session: AsyncSession, user_id: int, vacancy_id: str
) -> dict[str, Any] | None:
    record = await session.scalar(
        select(SentVacancy).where(
            SentVacancy.user_id == user_id, SentVacancy.vacancy_id == vacancy_id
        )
    )
    return record.payload if record else None


async def list_sent_for_subscription(
    session: AsyncSession, user_id: int, subscription_id: int
) -> list[SentVacancy]:
    result = await session.scalars(
        select(SentVacancy)
        .where(
            SentVacancy.user_id == user_id,
            SentVacancy.subscription_id == subscription_id,
        )
        .order_by(SentVacancy.sent_at)
    )
    return list(result)


# --- Избранное -------------------------------------------------------------
async def add_favorite(
    session: AsyncSession, user_id: int, payload: dict[str, Any]
) -> FavoriteVacancy:
    existing = await session.scalar(
        select(FavoriteVacancy).where(
            FavoriteVacancy.user_id == user_id,
            FavoriteVacancy.vacancy_id == payload["vacancy_id"],
        )
    )
    if existing:
        return existing
    favorite = FavoriteVacancy(
        user_id=user_id,
        vacancy_id=payload["vacancy_id"],
        title=payload.get("title", ""),
        employer_id=payload.get("employer_id"),
        employer_name=payload.get("employer_name"),
        salary_from=payload.get("salary_from"),
        salary_to=payload.get("salary_to"),
        currency=payload.get("currency"),
        area_name=payload.get("area_name"),
        url=payload.get("url", ""),
    )
    session.add(favorite)
    await session.flush()
    return favorite


async def list_favorites(session: AsyncSession, user_id: int) -> list[FavoriteVacancy]:
    result = await session.scalars(
        select(FavoriteVacancy)
        .where(FavoriteVacancy.user_id == user_id)
        .order_by(FavoriteVacancy.added_at.desc())
    )
    return list(result)


async def remove_favorite(
    session: AsyncSession, user_id: int, vacancy_id: str
) -> bool:
    result = await session.execute(
        delete(FavoriteVacancy).where(
            FavoriteVacancy.user_id == user_id, FavoriteVacancy.vacancy_id == vacancy_id
        )
    )
    return bool(result.rowcount)


# --- Чёрный список компаний -------------------------------------------------
async def add_blocked_employer(
    session: AsyncSession, user_id: int, employer_id: str, employer_name: str
) -> BlockedEmployer:
    existing = await session.scalar(
        select(BlockedEmployer).where(
            BlockedEmployer.user_id == user_id,
            BlockedEmployer.employer_id == employer_id,
        )
    )
    if existing:
        return existing
    blocked = BlockedEmployer(
        user_id=user_id, employer_id=employer_id, employer_name=employer_name
    )
    session.add(blocked)
    await session.flush()
    return blocked


async def list_blocked_employers(
    session: AsyncSession, user_id: int
) -> list[BlockedEmployer]:
    result = await session.scalars(
        select(BlockedEmployer)
        .where(BlockedEmployer.user_id == user_id)
        .order_by(BlockedEmployer.blocked_at.desc())
    )
    return list(result)


async def get_blocked_employer_ids(session: AsyncSession, user_id: int) -> set[str]:
    result = await session.scalars(
        select(BlockedEmployer.employer_id).where(BlockedEmployer.user_id == user_id)
    )
    return set(result)


async def remove_blocked_employer(session: AsyncSession, user_id: int, blocker_id: int) -> bool:
    result = await session.execute(
        delete(BlockedEmployer).where(
            BlockedEmployer.user_id == user_id, BlockedEmployer.id == blocker_id
        )
    )
    return bool(result.rowcount)


# --- Курсы валют -----------------------------------------------------------
async def get_cached_rates(session: AsyncSession) -> dict[str, float]:
    result = await session.scalars(select(CurrencyRate))
    return {row.code.upper(): float(row.rate) for row in result}


async def upsert_rates(session: AsyncSession, rates: dict[str, float], moment: datetime) -> None:
    for code, rate in rates.items():
        code = code.upper()
        existing = await session.get(CurrencyRate, code)
        if existing is None:
            session.add(CurrencyRate(code=code, rate=rate, updated_at=moment))
        else:
            existing.rate = rate
            existing.updated_at = moment
