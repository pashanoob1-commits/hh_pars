"""Конфигурация приложения (pydantic-settings, значения из .env)."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Настройки бота. Все значения читаются из переменных окружения / .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Telegram ---
    bot_token: str = Field(default="", description="Токен бота от @BotFather")

    # --- hh.ru API ---
    hh_api_base: str = "https://api.hh.ru"
    hh_user_agent: str = "hh-parser-bot/1.0 (you@example.com)"
    hh_min_request_interval: float = 0.5
    hh_max_retries: int = 5
    hh_per_page: int = 50
    hh_request_timeout: float = 30.0

    # --- База данных ---
    # Диалект не прошит: для PostgreSQL достаточно поменять DATABASE_URL.
    database_url: str = "sqlite+aiosqlite:///./data/bot.db"

    # --- Планировщик ---
    poll_interval_minutes: int = 15
    first_run_limit: int = 5

    # --- Бизнес-настройки ---
    base_currency: str = "RUR"
    max_subscriptions_per_user: int = 10
    currency_cache_hours: int = 24

    # --- Логирование ---
    log_level: str = "INFO"
    log_file: str = "./data/logs/bot.log"

    @field_validator("hh_user_agent")
    @classmethod
    def _validate_user_agent(cls, value: str) -> str:
        # hh.ru требует, чтобы User-Agent содержал контакт для связи.
        if "(" not in value or ")" not in value:
            raise ValueError(
                "HH_USER_AGENT должен иметь вид 'app/version (email)' — "
                "hh.ru требует контакт в User-Agent."
            )
        return value

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    return Settings()
