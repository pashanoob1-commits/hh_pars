-- Начальная схема hh-parser-bot (MVP).
-- Применяется автоматически через Base.metadata.create_all при старте,
-- этот файл — эквивалент для ручного применения / будущих Alembic-миграций.
-- Диалект-агностично: SQLite и PostgreSQL.

CREATE TABLE IF NOT EXISTS users (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id BIGINT      NOT NULL UNIQUE,
    username    VARCHAR(255),
    created_at  TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS subscriptions (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id          INTEGER      NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    query            TEXT         NOT NULL,
    area_id          INTEGER      NOT NULL,
    area_name        VARCHAR(255) NOT NULL DEFAULT '',
    experience       VARCHAR(64),
    employment       VARCHAR(64),
    salary_min       INTEGER,
    salary_max       INTEGER,
    only_with_salary BOOLEAN      NOT NULL DEFAULT FALSE,
    stop_words       TEXT         NOT NULL DEFAULT '[]',  -- JSON-массив
    is_active        BOOLEAN      NOT NULL DEFAULT TRUE,
    last_checked_at  TIMESTAMP,
    created_at       TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_subscription_identity UNIQUE (user_id, query, area_id)
);

CREATE TABLE IF NOT EXISTS sent_vacancies (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER     NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    subscription_id INTEGER     NOT NULL REFERENCES subscriptions (id) ON DELETE CASCADE,
    vacancy_id      VARCHAR(64) NOT NULL,
    payload         TEXT        NOT NULL DEFAULT '{}',  -- JSON-снимок вакансии
    sent_at         TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_sent_user_vacancy UNIQUE (user_id, vacancy_id)
);

CREATE TABLE IF NOT EXISTS favorite_vacancies (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
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
    added_at      TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_favorite_user_vacancy UNIQUE (user_id, vacancy_id)
);

CREATE TABLE IF NOT EXISTS blocked_employers (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER     NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    employer_id   VARCHAR(64) NOT NULL,
    employer_name TEXT        NOT NULL DEFAULT '',
    blocked_at    TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_blocked_user_employer UNIQUE (user_id, employer_id)
);

CREATE TABLE IF NOT EXISTS currencies (
    code       VARCHAR(8) PRIMARY KEY,
    rate       REAL       NOT NULL,
    updated_at TIMESTAMP  NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_subscriptions_user_id ON subscriptions (user_id);
CREATE INDEX IF NOT EXISTS ix_sent_vacancies_user_id ON sent_vacancies (user_id);
CREATE INDEX IF NOT EXISTS ix_sent_vacancies_vacancy_id ON sent_vacancies (vacancy_id);
