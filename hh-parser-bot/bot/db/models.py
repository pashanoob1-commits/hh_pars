"""ORM-модели (SQLAlchemy 2.0, диалект-агностичные типы)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import JSON


class Base(DeclarativeBase):
    """Базовый класс декларативных моделей."""


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    subscriptions: Mapped[list["Subscription"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", lazy="selectin"
    )


class Subscription(Base):
    __tablename__ = "subscriptions"
    __table_args__ = (
        UniqueConstraint("user_id", "query", "area_id", name="uq_subscription_identity"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    query: Mapped[str] = mapped_column(Text, nullable=False)
    area_id: Mapped[int] = mapped_column(Integer, nullable=False)
    area_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    experience: Mapped[str | None] = mapped_column(String(64), nullable=True)
    employment: Mapped[str | None] = mapped_column(String(64), nullable=True)
    salary_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    salary_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    only_with_salary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    stop_words: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="subscriptions")


class SentVacancy(Base):
    """Отправленные вакансии — основа дедупликации и лога для кнопок."""

    __tablename__ = "sent_vacancies"
    __table_args__ = (
        UniqueConstraint("user_id", "vacancy_id", name="uq_sent_user_vacancy"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    subscription_id: Mapped[int] = mapped_column(
        ForeignKey("subscriptions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    vacancy_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # Снимок вакансии (JSON) — нужен для кнопок «в избранное» / «скрыть компанию»
    # и для аналитики, чтобы не ходить лишний раз в API.
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class FavoriteVacancy(Base):
    __tablename__ = "favorite_vacancies"
    __table_args__ = (
        UniqueConstraint("user_id", "vacancy_id", name="uq_favorite_user_vacancy"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    vacancy_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    title: Mapped[str] = mapped_column(Text, nullable=False, default="")
    employer_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    employer_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    salary_from: Mapped[int | None] = mapped_column(Integer, nullable=True)
    salary_to: Mapped[int | None] = mapped_column(Integer, nullable=True)
    currency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    area_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    url: Mapped[str] = mapped_column(Text, nullable=False, default="")
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class BlockedEmployer(Base):
    __tablename__ = "blocked_employers"
    __table_args__ = (
        UniqueConstraint("user_id", "employer_id", name="uq_blocked_user_employer"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    employer_id: Mapped[str] = mapped_column(String(64), nullable=False)
    employer_name: Mapped[str] = mapped_column(Text, nullable=False, default="")
    blocked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class CurrencyRate(Base):
    """Кэш курсов валют к RUR (обновляется раз в CURRENCY_CACHE_HOURS)."""

    __tablename__ = "currencies"

    code: Mapped[str] = mapped_column(String(8), primary_key=True)
    rate: Mapped[float] = mapped_column(nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
