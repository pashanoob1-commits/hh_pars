"""FSM-состояния мастера подписки и управления стоп-словами."""

from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class AddSubscription(StatesGroup):
    query = State()
    area = State()
    area_search = State()
    experience = State()
    employment = State()
    salary_min = State()
    salary_max = State()
    only_with_salary = State()
    stop_words = State()
    confirm = State()


class StopWordsFlow(StatesGroup):
    waiting_words = State()
