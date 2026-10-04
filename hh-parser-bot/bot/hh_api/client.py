"""Асинхронный клиент официального API hh.ru (api.hh.ru).

Только официальный API — никакого HTML-скрапинга.
Особенности:
* обязательный User-Agent с контактом (требование hh.ru);
* соблюдение rate limit (минимальный интервал между запросами);
* retry с экспоненциальной задержкой на 429/5xx, поддержка Retry-After;
* отдельная ошибка на 403 Forbidden.
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from typing import Any

import httpx

from bot.config import Settings
from bot.hh_api.models import Area, HHVacancy, SearchParams

logger = logging.getLogger(__name__)


class HHAPIError(RuntimeError):
    """Базовая ошибка при обращении к API hh.ru."""


class HHForbiddenError(HHAPIError):
    """403: hh.ru ограничил доступ (проверьте User-Agent и лимиты)."""


class HHRateLimitError(HHAPIError):
    """429 после исчерпания всех retry."""


class HHClient:
    """Тонкий асинхронный клиент API hh.ru."""

    def __init__(
        self,
        settings: Settings,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._settings = settings
        self._base_url = settings.hh_api_base.rstrip("/")
        self._min_interval = max(settings.hh_min_request_interval, 0.0)
        self._max_retries = max(settings.hh_max_retries, 1)
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            base_url=self._base_url,
            timeout=settings.hh_request_timeout,
            headers={
                "User-Agent": settings.hh_user_agent,
                "Accept": "application/json",
            },
        )
        self._rate_lock = asyncio.Lock()
        self._last_request_at = 0.0
        self._areas_cache: list[Area] | None = None

    # --- lifecycle -----------------------------------------------------
    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def __aenter__(self) -> "HHClient":
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.close()

    # --- внутреннее ----------------------------------------------------
    async def _throttle(self) -> None:
        """Выдерживает минимальный интервал между запросами."""
        if self._min_interval <= 0:
            return
        async with self._rate_lock:
            now = time.monotonic()
            elapsed = now - self._last_request_at
            if elapsed < self._min_interval:
                await asyncio.sleep(self._min_interval - elapsed)
            self._last_request_at = time.monotonic()

    async def _request(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """GET-запрос с retry и обработкой типовых ошибок hh.ru."""
        last_error: Exception | None = None

        for attempt in range(self._max_retries):
            await self._throttle()
            try:
                response = await self._client.get(path, params=params)
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_error = exc
                await self._sleep_backoff(attempt)
                continue

            status = response.status_code
            if status == 200:
                return response.json()

            if status == 403:
                raise HHForbiddenError(
                    "hh.ru вернул 403 Forbidden: проверьте User-Agent и соблюдение "
                    "правил использования API."
                )

            if status == 429 or status >= 500:
                last_error = HHRateLimitError(f"hh.ru вернул {status}")
                delay = self._retry_after(response) or self._backoff_delay(attempt)
                logger.warning(
                    "hh.ru ответил %s, повтор через %.1f c (попытка %s/%s)",
                    status,
                    delay,
                    attempt + 1,
                    self._max_retries,
                )
                await asyncio.sleep(delay)
                continue

            raise HHAPIError(f"Неожиданный ответ API hh.ru: {status} {response.text[:200]}")

        raise HHAPIError(f"Не удалось выполнить запрос к hh.ru: {last_error}")

    @staticmethod
    def _retry_after(response: httpx.Response) -> float | None:
        value = response.headers.get("Retry-After")
        if not value:
            return None
        try:
            return float(value)
        except ValueError:
            return None

    def _backoff_delay(self, attempt: int) -> float:
        """Экспоненциальная задержка с джиттером."""
        base = 1.0
        return base * (2**attempt) + random.uniform(0, 0.5)

    async def _sleep_backoff(self, attempt: int) -> None:
        await asyncio.sleep(self._backoff_delay(attempt))

    # --- публичное API --------------------------------------------------
    async def search_vacancies(self, params: SearchParams) -> list[HHVacancy]:
        """Поиск вакансий. Возвращает нормализованный список."""
        payload = await self._request("/vacancies", params=params.to_query())
        items = payload.get("items", [])
        return [HHVacancy.from_api(item) for item in items]

    async def get_vacancy(self, vacancy_id: str) -> dict[str, Any] | None:
        """Детальная карточка вакансии (может быть недоступна для архивных)."""
        try:
            return await self._request(f"/vacancies/{vacancy_id}")
        except HHAPIError as exc:
            logger.warning("Не удалось получить вакансию %s: %s", vacancy_id, exc)
            return None

    async def get_areas(self) -> list[Area]:
        """Плоский список всех регионов (кэшируется в памяти процесса)."""
        if self._areas_cache is not None:
            return self._areas_cache

        payload = await self._request("/areas")
        result: list[Area] = []

        def walk(nodes: list[dict[str, Any]], parent: str | None = None) -> None:
            for node in nodes:
                name = node.get("name")
                if name:
                    result.append(Area(id=int(node["id"]), name=name, parent_name=parent))
                children = node.get("areas") or []
                if children:
                    walk(children, name)

        walk(payload if isinstance(payload, list) else payload.get("areas", []))
        self._areas_cache = result
        return result

    async def find_areas(self, query: str, limit: int = 10) -> list[Area]:
        """Поиск региона по названию (подстрока, регистр не важен)."""
        needle = query.strip().lower()
        if not needle:
            return []
        areas = await self.get_areas()
        exact = [a for a in areas if a.name.lower() == needle]
        startswith = [
            a for a in areas if a.name.lower().startswith(needle) and a not in exact
        ]
        contains = [
            a
            for a in areas
            if needle in a.name.lower() and a not in exact and a not in startswith
        ]
        return (exact + startswith + contains)[:limit]

    async def get_currency_rates(self) -> dict[str, float]:
        """Курсы валют к RUR из /dictionaries: {код: сколько RUR за 1 единицу}."""
        payload = await self._request("/dictionaries")
        rates: dict[str, float] = {}
        for item in payload.get("currency", []):
            code = item.get("code") or item.get("abbr")
            if not code:
                continue
            rate = item.get("rate")
            if rate is None:
                continue
            nominal = item.get("nominal") or 1
            try:
                rates[str(code).upper()] = float(rate) / float(nominal)
            except (TypeError, ValueError, ZeroDivisionError):
                continue
        rates.setdefault("RUR", 1.0)
        return rates
