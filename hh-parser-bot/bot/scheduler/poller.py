"""Планировщик: периодический опрос hh.ru по активным подпискам."""

from __future__ import annotations

import logging

from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.config import Settings
from bot.db import repositories as repo
from bot.db.models import Subscription, User
from bot.hh_api.client import HHAPIError, HHClient
from bot.services.currency import CurrencyService
from bot.services.dedup import filter_new_vacancies
from bot.services.filters import apply_subscription_filters
from bot.services.formatter import format_vacancy_message, vacancy_to_payload
from bot.services.notifier import Notifier
from bot.services.subscriptions import SubscriptionService
from bot.utils.time import utcnow

logger = logging.getLogger(__name__)


class VacancyPoller:
    """Опрашивает API hh.ru и рассылает только новые вакансии."""

    def __init__(
        self,
        *,
        bot: Bot,
        settings: Settings,
        session_factory: async_sessionmaker[AsyncSession],
        client: HHClient,
    ) -> None:
        self._settings = settings
        self._session_factory = session_factory
        self._client = client
        self._notifier = Notifier(bot)

    async def poll_once(self) -> int:
        """Один проход по всем активным подпискам. Возвращает число отправленных."""
        async with self._session_factory() as session:
            subscription_ids = [
                sub.id for sub in await repo.list_active_subscriptions(session)
            ]

        total_sent = 0
        for subscription_id in subscription_ids:
            try:
                total_sent += await self._poll_subscription(subscription_id)
            except HHAPIError as exc:
                logger.error("Подписка %s: ошибка API hh.ru: %s", subscription_id, exc)
            except Exception:  # noqa: BLE001 — одна битая подписка не должна рушить цикл
                logger.exception("Подписка %s: непредвиденная ошибка опроса", subscription_id)

        if total_sent:
            logger.info("Отправлено новых вакансий: %s", total_sent)
        return total_sent

    async def _poll_subscription(self, subscription_id: int) -> int:
        async with self._session_factory() as session:
            subscription = await session.get(Subscription, subscription_id)
            if subscription is None or not subscription.is_active:
                return 0
            user = await session.get(User, subscription.user_id)
            if user is None:
                return 0

            vacancies = await self._fetch(subscription)
            vacancies = [v for v in vacancies if not v.archived]

            blocked_ids = await repo.get_blocked_employer_ids(session, subscription.user_id)
            filtered = apply_subscription_filters(
                vacancies,
                stop_words=list(subscription.stop_words or []),
                blocked_employer_ids=blocked_ids,
                salary_max=subscription.salary_max,
                published_after=subscription.last_checked_at,
            )
            fresh = await filter_new_vacancies(session, subscription.user_id, filtered)

            first_run = subscription.last_checked_at is None
            if first_run and len(fresh) > self._settings.first_run_limit:
                # Первый запуск: не заваливаем пользователя, берём самые свежие.
                fresh = fresh[: self._settings.first_run_limit]

            sent = await self._dispatch(session, user, subscription, fresh)
            subscription.last_checked_at = utcnow()
            await session.commit()

            if sent:
                logger.info(
                    "Подписка %s (user %s): отправлено %s вакансий",
                    subscription.id,
                    user.telegram_id,
                    sent,
                )
            return sent

    async def _fetch(self, subscription: Subscription):
        params = SubscriptionService.build_search_params(
            subscription, per_page=self._settings.hh_per_page
        )
        return await self._client.search_vacancies(params)

    async def _dispatch(
        self,
        session: AsyncSession,
        user: User,
        subscription: Subscription,
        vacancies: list,
    ) -> int:
        if not vacancies:
            return 0

        currency = CurrencyService(session, self._client, self._settings)
        subscription_title = f"«{subscription.query}» ({subscription.area_name})"
        sent = 0

        for vacancy in vacancies:
            salary = await currency.convert_salary(
                vacancy.salary_from, vacancy.salary_to, vacancy.salary_currency
            )
            text = format_vacancy_message(
                vacancy, salary, subscription_title=subscription_title
            )
            delivered = await self._notifier.send_vacancy(
                user.telegram_id,
                text,
                vacancy_id=vacancy.id,
                url=vacancy.alternate_url or None,
                employer_id=vacancy.employer_id,
            )
            if not delivered:
                continue

            await repo.mark_sent(
                session,
                user_id=user.id,
                subscription_id=subscription.id,
                vacancy_id=vacancy.id,
                payload=vacancy_to_payload(vacancy, salary),
            )
            sent += 1

        return sent
