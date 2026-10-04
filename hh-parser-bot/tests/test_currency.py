"""Тесты конвертации валют."""

from __future__ import annotations

import pytest

from bot.services.currency import CurrencyService, convert_amount

RATES = {"RUR": 1.0, "USD": 90.0, "EUR": 100.0, "KZT": 0.2}


def test_convert_same_currency():
    assert convert_amount(1000, "RUR", "RUR", RATES) == 1000


def test_convert_usd_to_rur():
    assert convert_amount(10, "USD", "RUR", RATES) == 900


def test_convert_usd_to_kzt_cross_rate():
    # 10 USD -> 900 RUR -> 900 / 0.2 = 4500 KZT
    assert convert_amount(10, "USD", "KZT", RATES) == 4500


def test_convert_none_amount():
    assert convert_amount(None, "USD", "RUR", RATES) is None


def test_convert_unknown_currency_returns_original():
    assert convert_amount(500, "XYZ", "RUR", RATES) == 500


def test_convert_missing_currency_code_defaults_to_rur():
    assert convert_amount(500, None, "RUR", RATES) == 500


class FakeClient:
    def __init__(self, rates):
        self.rates = rates
        self.calls = 0

    async def get_currency_rates(self):
        self.calls += 1
        return self.rates


async def test_currency_service_caches_rates(settings, session):
    client = FakeClient({"RUR": 1.0, "USD": 93.0})
    service = CurrencyService(session, client, settings)

    first = await service.get_rates()
    assert first["USD"] == pytest.approx(93.0)

    second = await service.get_rates()
    assert second["USD"] == pytest.approx(93.0)
    # Второй раз курсы берутся из кэша БД, без обращения к API.
    assert client.calls == 1
    await session.commit()

    # Новый сервис с той же сессией тоже видит кэш.
    other = CurrencyService(session, FakeClient({}), settings)
    cached = await other.get_rates()
    assert cached["USD"] == pytest.approx(93.0)


async def test_convert_salary_to_base_currency(settings, session):
    client = FakeClient({"RUR": 1.0, "USD": 90.0})
    service = CurrencyService(session, client, settings)

    salary = await service.convert_salary(1000, 2000, "USD")
    assert salary.currency == "RUR"
    assert salary.from_amount == 90000
    assert salary.to_amount == 180000
