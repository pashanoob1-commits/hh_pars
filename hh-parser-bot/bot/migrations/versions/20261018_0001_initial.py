"""Начальная схема: users, subscriptions, sent/favorite/blocked, currencies.

Revision ID: 20261018_0001
Revises:
Create Date: 2026-10-18
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261018_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("telegram_id", name="uq_users_telegram_id"),
    )
    op.create_index("ix_users_telegram_id", "users", ["telegram_id"], unique=False)

    op.create_table(
        "subscriptions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("area_id", sa.Integer(), nullable=False),
        sa.Column("area_name", sa.String(length=255), nullable=False),
        sa.Column("experience", sa.String(length=64), nullable=True),
        sa.Column("employment", sa.String(length=64), nullable=True),
        sa.Column("salary_min", sa.Integer(), nullable=True),
        sa.Column("salary_max", sa.Integer(), nullable=True),
        sa.Column("only_with_salary", sa.Boolean(), nullable=False),
        sa.Column("stop_words", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id", "query", "area_id", name="uq_subscription_identity"
        ),
    )
    op.create_index(
        "ix_subscriptions_user_id", "subscriptions", ["user_id"], unique=False
    )

    op.create_table(
        "sent_vacancies",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("subscription_id", sa.Integer(), nullable=False),
        sa.Column("vacancy_id", sa.String(length=64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column(
            "sent_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["subscription_id"], ["subscriptions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "vacancy_id", name="uq_sent_user_vacancy"),
    )
    op.create_index(
        "ix_sent_vacancies_user_id", "sent_vacancies", ["user_id"], unique=False
    )
    op.create_index(
        "ix_sent_vacancies_subscription_id",
        "sent_vacancies",
        ["subscription_id"],
        unique=False,
    )
    op.create_index(
        "ix_sent_vacancies_vacancy_id", "sent_vacancies", ["vacancy_id"], unique=False
    )

    op.create_table(
        "favorite_vacancies",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("vacancy_id", sa.String(length=64), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("employer_id", sa.String(length=64), nullable=True),
        sa.Column("employer_name", sa.Text(), nullable=True),
        sa.Column("salary_from", sa.Integer(), nullable=True),
        sa.Column("salary_to", sa.Integer(), nullable=True),
        sa.Column("currency", sa.String(length=8), nullable=True),
        sa.Column("area_name", sa.String(length=255), nullable=True),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column(
            "added_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "vacancy_id", name="uq_favorite_user_vacancy"),
    )
    op.create_index(
        "ix_favorite_vacancies_user_id", "favorite_vacancies", ["user_id"], unique=False
    )
    op.create_index(
        "ix_favorite_vacancies_vacancy_id",
        "favorite_vacancies",
        ["vacancy_id"],
        unique=False,
    )

    op.create_table(
        "blocked_employers",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("employer_id", sa.String(length=64), nullable=False),
        sa.Column("employer_name", sa.Text(), nullable=False),
        sa.Column(
            "blocked_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "employer_id", name="uq_blocked_user_employer"),
    )
    op.create_index(
        "ix_blocked_employers_user_id", "blocked_employers", ["user_id"], unique=False
    )

    op.create_table(
        "currencies",
        sa.Column("code", sa.String(length=8), nullable=False),
        sa.Column("rate", sa.Double(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("code"),
    )


def downgrade() -> None:
    op.drop_table("currencies")
    op.drop_table("blocked_employers")
    op.drop_table("favorite_vacancies")
    op.drop_table("sent_vacancies")
    op.drop_table("subscriptions")
    op.drop_table("users")
