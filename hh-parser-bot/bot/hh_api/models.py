"""Модели данных API hh.ru (pydantic)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _clean(value: str | None) -> str | None:
    """Убирает неразрывные пробелы из строк API."""
    if value is None:
        return None
    return value.replace("\xa0", " ").strip()


class Area(BaseModel):
    """Регион из /areas."""

    model_config = ConfigDict(frozen=True)

    id: int
    name: str
    parent_name: str | None = None


class HHVacancy(BaseModel):
    """Нормализованное представление вакансии из поисковой выдачи."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    name: str
    employer_id: str | None = None
    employer_name: str | None = None
    salary_from: int | None = None
    salary_to: int | None = None
    salary_currency: str | None = None
    area_name: str | None = None
    experience: str | None = None
    employment: str | None = None
    snippet_requirement: str | None = None
    snippet_responsibility: str | None = None
    alternate_url: str = ""
    published_at: datetime | None = None
    archived: bool = False
    key_skills: list[str] = Field(default_factory=list)

    @field_validator("name", "employer_name", "area_name", "experience", "employment")
    @classmethod
    def _strip(cls, value: str | None) -> str | None:
        return _clean(value)

    @field_validator("snippet_requirement", "snippet_responsibility")
    @classmethod
    def _strip_snippet(cls, value: str | None) -> str | None:
        return _clean(value)

    @property
    def searchable_text(self) -> str:
        """Текст, по которому ищутся стоп-слова."""
        parts = [self.name, self.snippet_requirement, self.snippet_responsibility]
        return " ".join(p for p in parts if p).lower()

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> HHVacancy:
        """Собирает модель из элемента выдачи API hh.ru."""
        salary = data.get("salary") or {}
        employer = data.get("employer") or {}
        area = data.get("area") or {}
        experience = data.get("experience") or {}
        employment = data.get("employment") or {}
        snippet = data.get("snippet") or {}
        skills = data.get("key_skills") or []

        published_raw = data.get("published_at")
        published_at: datetime | None = None
        if published_raw:
            try:
                published_at = datetime.fromisoformat(published_raw)
            except ValueError:
                published_at = None

        return cls(
            id=str(data.get("id")),
            name=data.get("name") or "",
            employer_id=str(employer["id"]) if employer.get("id") is not None else None,
            employer_name=employer.get("name"),
            salary_from=salary.get("from"),
            salary_to=salary.get("to"),
            salary_currency=salary.get("currency"),
            area_name=area.get("name"),
            experience=experience.get("name"),
            employment=employment.get("name"),
            snippet_requirement=snippet.get("requirement"),
            snippet_responsibility=snippet.get("responsibility"),
            alternate_url=data.get("alternate_url") or "",
            published_at=published_at,
            archived=bool(data.get("archived", False)),
            key_skills=[
                item.get("name", "") for item in skills if isinstance(item, dict)
            ],
        )


class SalaryRange(BaseModel):
    """Нормализованная зарплатная вилка (в целевой валюте)."""

    from_amount: int | None = None
    to_amount: int | None = None
    currency: str = "RUR"
    gross: bool | None = None


class SearchParams(BaseModel):
    """Параметры поиска вакансий (транслируются в query API hh.ru)."""

    text: str
    area: int | None = None
    experience: str | None = None
    employment: str | None = None
    salary_from: int | None = None
    salary_to: int | None = None
    only_with_salary: bool = False
    order_by: str = "publication_time"
    per_page: int = 50
    page: int = 0

    def to_query(self) -> dict[str, Any]:
        query: dict[str, Any] = {
            "text": self.text,
            "order_by": self.order_by,
            "per_page": self.per_page,
            "page": self.page,
        }
        if self.area is not None:
            query["area"] = self.area
        if self.experience:
            query["experience"] = self.experience
        if self.employment:
            query["employment"] = self.employment
        if self.salary_from is not None:
            query["salary"] = self.salary_from
            query["only_with_salary"] = True
        if self.only_with_salary:
            query["only_with_salary"] = True
        return query
