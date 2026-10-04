"""Парсинг пользовательского ввода (вынесено для тестируемости)."""

from __future__ import annotations

import re

SKIP_TOKENS = {"-", "нет", "пропустить", "skip", "0"}

_WORD_SPLIT = re.compile(r"[,;\n]+")


def parse_positive_int(text: str) -> int | None:
    """Парсит неотрицательное целое; None — если это сигнал «пропустить»."""
    value = text.strip().replace(" ", "").replace("\u00a0", "")
    if value.lower() in SKIP_TOKENS:
        return None
    if not value.isdigit():
        raise ValueError("Нужно целое неотрицательное число или «-», чтобы пропустить.")
    return int(value)


def parse_stop_words(text: str) -> list[str]:
    """Разбирает строку стоп-слов: через запятую, точку с запятой или перевод строки."""
    if text.strip().lower() in SKIP_TOKENS:
        return []
    words: list[str] = []
    for chunk in _WORD_SPLIT.split(text):
        word = chunk.strip().lower()
        if word and word not in SKIP_TOKENS and word not in words:
            words.append(word)
    return words


def format_stop_words(stop_words: list[str]) -> str:
    return ", ".join(stop_words) if stop_words else "нет"
