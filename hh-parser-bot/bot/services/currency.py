"""Конвертация зарплат в единую валюту с суточным кэшем курсов."""

from __future__ import annotations

import logging
from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import Settings
from bot.db import repositories as repo
from bot.hh_api.client import HHAPIError, HHClient
from bot.hh_api.models import SalaryRange
from bot.utils.time import ensure_aware, utcnow

logger = logging.getLogger(__name__)


def convert_amount(
    amount: int | None,
    from_currency: str | None,
    to_currency: str,
    rates: dict[str, float],
) -> int | None:
    """Переводит сумму из одной валюты в другую через курс к RUR.

    rates: {код: сколько RUR стоит 1 единица валюты}.
    """
    if amount is None:
        return None

    from_code = (from_currency or "RUR").upper()
    to_code = to_currency.upper()
    if from_code == to_code:
        return int(amount)

    from_rate = rates.get(from_code)
    to_rate = rates.get(to_code)
    if not from_rate or not to_rate:
        # Неизвестная валюта — отдаём как есть, чтобы не потерять данные.
        return int(amount)

    value_in_rur = float(amount) * float(from_rate)
    return int(round(value_in_rur / float(to_rate)))


class CurrencyService:
    """Курсы валют из /dictionaries API hh.ru, кэшируются на CURRENCY_CACHE_HOURS."""

    def __init__(self, session: AsyncSession, client: HHClient, settings: Settings) -> None:
        self._session = session
        self._client = client
        self._settings = settings
        self._memory_cache: dict[str, float] | None = None

    async def get_rates(self, force_refresh: bool = False) -> dict[str, float]:
        if self._memory_cache is not None and not force_refresh:
            return self._memory_cache

        cached = await repo.get_cached_rates(self._session)
        if cached and not force_refresh and not await self._is_stale(cached):
            self._memory_cache = cached
            return cached

        try:
            rates = await self._client.get_currency_rates()
        except HHAPIError as exc:
            logger.warning("Не удалось обновить курсы валют: %s", exc)
            self._memory_cache = cached or {"RUR": 1.0}
            return self._memory_cache

        if rates:
            await repo.upsert_rates(self._session, rates, utcnow())
            cached = rates
        self._memory_cache = cached or {"RUR": 1.0}
        return self._memory_cache

    async def _is_stale(self, cached: dict[str, float]) -> bool:
        """Проверяет дату обновления курсов в таблице currencies."""
        from sqlalchemy import select

        from bot.db.models import CurrencyRate

        row = await self._session.scalar(select(CurrencyRate))
        if row is None:
            return True
        max_age = timedelta(hours=self._settings.currency_cache_hours)
        return utcnow() - ensure_aware(row.updated_at) > max_age

    async def convert_salary(
        self, salary_from: int | None, salary_to: int | None, currency: str | None
    ) -> SalaryRange:
        rates = await self.get_rates()
        target = self._settings.base_currency
        return SalaryRange(
            from_amount=convert_amount(salary_from, currency, target, rates),
            to_amount=convert_amount(salary_to, currency, target, rates),
            currency=target,
        )
