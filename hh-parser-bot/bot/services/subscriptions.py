"""Сервис подписок: бизнес-правила поверх репозитория подписок."""

from __future__ import annotations

from typing import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import Settings
from bot.db import repositories as repo
from bot.db.models import Subscription
from bot.hh_api.models import SearchParams
from bot.services.dictionaries import experience_label, employment_label


class SubscriptionError(Exception):
    """Нарушение бизнес-правила при работе с подписками."""


class SubscriptionLimitReached(SubscriptionError):
    """Достигнут лимит подписок пользователя."""


class DuplicateSubscription(SubscriptionError):
    """Подписка с таким запросом и регионом уже существует."""


class SubscriptionService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._settings = settings

    async def create(
        self,
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
        query = query.strip()
        if not query:
            raise SubscriptionError("Поисковый запрос не может быть пустым.")
        if salary_min and salary_max and salary_min > salary_max:
            raise SubscriptionError("Минимальная зарплата больше максимальной.")

        count = await repo.count_subscriptions(self._session, user_id)
        if count >= self._settings.max_subscriptions_per_user:
            raise SubscriptionLimitReached(
                f"Достигнут лимит подписок "
                f"({self._settings.max_subscriptions_per_user}). "
                "Удалите ненужные через /list и /del."
            )

        existing = await repo.list_subscriptions(self._session, user_id)
        for sub in existing:
            if sub.query.lower() == query.lower() and sub.area_id == area_id:
                raise DuplicateSubscription(
                    f"Подписка «{sub.query}» для этого региона уже существует "
                    f"(id={sub.id})."
                )

        return await repo.create_subscription(
            self._session,
            user_id,
            query=query,
            area_id=area_id,
            area_name=area_name,
            experience=experience,
            employment=employment,
            salary_min=salary_min,
            salary_max=salary_max,
            only_with_salary=only_with_salary or salary_min is not None,
            stop_words=stop_words,
        )

    async def list_for_user(self, user_id: int) -> list[Subscription]:
        return await repo.list_subscriptions(self._session, user_id)

    async def get(self, user_id: int, subscription_id: int) -> Subscription | None:
        return await repo.get_subscription(self._session, user_id, subscription_id)

    async def delete(self, user_id: int, subscription_id: int) -> bool:
        subscription = await self.get(user_id, subscription_id)
        if subscription is None:
            return False
        await repo.delete_subscription(self._session, subscription)
        return True

    async def set_active(self, user_id: int, subscription_id: int, active: bool) -> bool:
        subscription = await self.get(user_id, subscription_id)
        if subscription is None:
            return False
        subscription.is_active = active
        return True

    async def set_stop_words(
        self, user_id: int, subscription_id: int, stop_words: Sequence[str]
    ) -> bool:
        subscription = await self.get(user_id, subscription_id)
        if subscription is None:
            return False
        await repo.update_stop_words(self._session, subscription, stop_words)
        return True

    @staticmethod
    def build_search_params(subscription: Subscription, per_page: int = 50) -> SearchParams:
        """Превращает подписку в параметры запроса к API hh.ru."""
        return SearchParams(
            text=subscription.query,
            area=subscription.area_id,
            experience=subscription.experience,
            employment=subscription.employment,
            salary_from=subscription.salary_min,
            salary_to=subscription.salary_max,
            only_with_salary=subscription.only_with_salary,
            order_by="publication_time",
            per_page=per_page,
            page=0,
        )


def describe_subscription(subscription: Subscription) -> str:
    """Краткое человекочитаемое описание подписки."""
    parts = [f"«{subscription.query}»", subscription.area_name or f"area={subscription.area_id}"]
    if subscription.experience:
        parts.append(f"опыт: {experience_label(subscription.experience)}")
    if subscription.employment:
        parts.append(f"занятость: {employment_label(subscription.employment)}")
    if subscription.salary_min or subscription.salary_max:
        low = subscription.salary_min or "…"
        high = subscription.salary_max or "…"
        parts.append(f"зарплата: {low}–{high}")
    if subscription.only_with_salary:
        parts.append("только с зарплатой")
    if subscription.stop_words:
        parts.append(f"стоп-слова: {', '.join(subscription.stop_words)}")
    return "; ".join(parts)
