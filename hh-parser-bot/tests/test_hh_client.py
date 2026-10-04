"""Тесты клиента API hh.ru с замоканным httpx (respx)."""

from __future__ import annotations

import httpx
import pytest
import respx

from bot.hh_api.client import HHClient, HHForbiddenError
from bot.hh_api.models import SearchParams

VACANCY = {
    "id": "12345",
    "name": "Python\u00a0разработчик",
    "employer": {"id": "777", "name": "ООО Тест"},
    "salary": {"from": 100000, "to": 150000, "currency": "RUR", "gross": False},
    "area": {"id": 1, "name": "Москва"},
    "experience": {"id": "between1And3", "name": "От 1 до 3 лет"},
    "employment": {"id": "full", "name": "Полная занятость"},
    "snippet": {"requirement": "Python, FastAPI", "responsibility": "Разработка"},
    "alternate_url": "https://hh.ru/vacancy/12345",
    "published_at": "2024-05-01T12:00:00+0300",
    "archived": False,
    "key_skills": [{"name": "Python"}],
}

AREAS = [
    {
        "id": "113",
        "name": "Россия",
        "areas": [
            {"id": "1", "name": "Москва", "areas": []},
            {"id": "2", "name": "Санкт-Петербург", "areas": []},
        ],
    },
    {"id": "40", "name": "Казахстан", "areas": [{"id": "159", "name": "Алматы", "areas": []}]},
]

DICTIONARIES = {
    "currency": [
        {"code": "RUR", "rate": 1, "nominal": 1},
        {"code": "USD", "rate": 90.5, "nominal": 1},
        {"code": "KZT", "rate": 0.19, "nominal": 1},
    ]
}


@respx.mock
async def test_search_vacancies_normalizes_response(settings):
    route = respx.get("https://api.hh.ru/vacancies").mock(
        return_value=httpx.Response(200, json={"items": [VACANCY]})
    )

    async with HHClient(settings) as client:
        vacancies = await client.search_vacancies(SearchParams(text="python", area=1))

    assert len(vacancies) == 1
    vacancy = vacancies[0]
    assert vacancy.id == "12345"
    assert vacancy.name == "Python разработчик"  # неразрывный пробел почищен
    assert vacancy.employer_name == "ООО Тест"
    assert (vacancy.salary_from, vacancy.salary_to) == (100000, 150000)
    assert vacancy.searchable_text.startswith("python разработчик")
    assert vacancy.published_at is not None

    request = route.calls[0].request
    assert "hh-parser-bot" in request.headers["user-agent"]
    assert request.url.params["order_by"] == "publication_time"


@respx.mock
async def test_search_vacancies_retries_on_429(settings, monkeypatch):
    # Убираем реальные паузы в тестах.
    monkeypatch.setattr(HHClient, "_backoff_delay", lambda self, attempt: 0.0)
    route = respx.get("https://api.hh.ru/vacancies").mock(
        side_effect=[
            httpx.Response(429, headers={"Retry-After": "0"}),
            httpx.Response(200, json={"items": [VACANCY]}),
        ]
    )

    async with HHClient(settings) as client:
        vacancies = await client.search_vacancies(SearchParams(text="python"))

    assert len(vacancies) == 1
    assert route.call_count == 2


@respx.mock
async def test_search_vacancies_raises_on_403(settings):
    respx.get("https://api.hh.ru/vacancies").mock(return_value=httpx.Response(403))

    async with HHClient(settings) as client:
        with pytest.raises(HHForbiddenError):
            await client.search_vacancies(SearchParams(text="python"))


@respx.mock
async def test_areas_are_flattened_and_searchable(settings):
    respx.get("https://api.hh.ru/areas").mock(
        return_value=httpx.Response(200, json=AREAS)
    )

    async with HHClient(settings) as client:
        areas = await client.get_areas()
        assert {area.name for area in areas} >= {"Россия", "Москва", "Алматы"}

        found = await client.find_areas("моск")
        assert found[0].id == 1 and found[0].name == "Москва"

        # повторный вызов использует кэш (запрос один)
        await client.get_areas()

    assert respx.calls.call_count == 1


@respx.mock
async def test_currency_rates_from_dictionaries(settings):
    respx.get("https://api.hh.ru/dictionaries").mock(
        return_value=httpx.Response(200, json=DICTIONARIES)
    )

    async with HHClient(settings) as client:
        rates = await client.get_currency_rates()

    assert rates["RUR"] == 1.0
    assert rates["USD"] == pytest.approx(90.5)
    assert rates["KZT"] == pytest.approx(0.19)
