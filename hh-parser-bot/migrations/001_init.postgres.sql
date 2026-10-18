-- Начальная схема hh-parser-bot для PostgreSQL (ручной bootstrap).
-- Рекомендуемый способ — Alembic: `python -m bot.db.migrate upgrade`.
-- Этот скрипт — эквивалент миграции 20261018_0001 для DBA/ручного развёртывания.
-- Для SQLite используйте 001_init.sql.

CREATE TABLE IF NOT EXISTS users (
    id          SERIAL PRIMARY KEY,
    telegram_id BIGINT       NOT NULL,
    username    VARCHAR(255),
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT now(),
    CONSTRAINT uq_users_telegram_id UNIQUE (telegram_id)
);
CREATE INDEX IF NOT EXISTS ix_users_telegram_id ON users (telegram_id);

CREATE TABLE IF NOT EXISTS subscriptions (
    id               SERIAL PRIMARY KEY,
    user_id          INTEGER      NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    query            TEXT         NOT NULL,
    area_id          INTEGER      NOT NULL,
    area_name        VARCHAR(255) NOT NULL DEFAULT '',
    experience       VARCHAR(64),
    employment       VARCHAR(64),
    salary_min       INTEGER,
    salary_max       INTEGER,
    only_with_salary BOOLEAN      NOT NULL DEFAULT FALSE,
    stop_words       JSONB        NOT NULL DEFAULT '[]'::jsonb,
    is_active        BOOLEAN      NOT NULL DEFAULT TRUE,
    last_checked_at  TIMESTAMPTZ,
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT now(),
    CONSTRAINT uq_subscription_identity UNIQUE (user_id, query, area_id)
);
CREATE INDEX IF NOT EXISTS ix_subscriptions_user_id ON subscriptions (user_id);

CREATE TABLE IF NOT EXISTS sent_vacancies (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER     NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    subscription_id INTEGER     NOT NULL REFERENCES subscriptions (id) ON DELETE CASCADE,
    vacancy_id      VARCHAR(64) NOT NULL,
    payload         JSONB       NOT NULL DEFAULT '{}'::jsonb,
    sent_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_sent_user_vacancy UNIQUE (user_id, vacancy_id)
);
CREATE INDEX IF NOT EXISTS ix_sent_vacancies_user_id ON sent_vacancies (user_id);
CREATE INDEX IF NOT EXISTS ix_sent_vacancies_subscription_id ON sent_vacancies (subscription_id);
CREATE INDEX IF NOT EXISTS ix_sent_vacancies_vacancy_id ON sent_vacancies (vacancy_id);

CREATE TABLE IF NOT EXISTS favorite_vacancies (
    id            SERIAL PRIMARY KEY,
    user_id       INTEGER     NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    vacancy_id    VARCHAR(64) NOT NULL,
    title         TEXT        NOT NULL DEFAULT '',
    employer_id   VARCHAR(64),
    employer_name TEXT,
    salary_from   INTEGER,
    salary_to     INTEGER,
    currency      VARCHAR(8),
    area_name     VARCHAR(255),
    url           TEXT        NOT NULL DEFAULT '',
    added_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_favorite_user_vacancy UNIQUE (user_id, vacancy_id)
);
CREATE INDEX IF NOT EXISTS ix_favorite_vacancies_user_id ON favorite_vacancies (user_id);
CREATE INDEX IF NOT EXISTS ix_favorite_vacancies_vacancy_id ON favorite_vacancies (vacancy_id);

CREATE TABLE IF NOT EXISTS blocked_employers (
    id            SERIAL PRIMARY KEY,
    user_id       INTEGER     NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    employer_id   VARCHAR(64) NOT NULL,
    employer_name TEXT        NOT NULL DEFAULT '',
    blocked_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_blocked_user_employer UNIQUE (user_id, employer_id)
);
CREATE INDEX IF NOT EXISTS ix_blocked_employers_user_id ON blocked_employers (user_id);

CREATE TABLE IF NOT EXISTS currencies (
    code       VARCHAR(8) PRIMARY KEY,
    rate       DOUBLE PRECISION NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Версия схемы для Alembic (если применяете SQL вручную, зафиксируйте её,
-- чтобы последующие `alembic upgrade` не пытались создать таблицы повторно):
-- CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(32) PRIMARY KEY);
-- INSERT INTO alembic_version (version_num) VALUES ('20261018_0001');
