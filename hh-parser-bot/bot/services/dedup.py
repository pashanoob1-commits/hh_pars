"""Дедупликация: вакансия отправляется пользователю только один раз."""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from bot.db import repositories as repo
from bot.hh_api.models import HHVacancy


async def filter_new_vacancies(
    session: AsyncSession, user_id: int, vacancies: Iterable[HHVacancy]
) -> list[HHVacancy]:
    """Убирает вакансии, которые уже отправлялись этому пользователю."""
    items = list(vacancies)
    if not items:
        return []

    ids: Sequence[str] = [v.id for v in items]
    already_sent = await repo.get_sent_vacancy_ids(session, user_id, ids)
    return [v for v in items if v.id not in already_sent]
