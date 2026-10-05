# hh-parser-bot 🤖

Мультипользовательский Telegram-бот для мониторинга новых вакансий на **hh.ru**
через **официальный API** (`api.hh.ru`). Каждый пользователь настраивает свои
поисковые подписки и получает уведомления только о новых вакансиях.

> Никакого HTML-скрапинга: только официальный API. HTML-парсеры теряют до ~60%
> вакансий со страницы поиска и ломаются при изменении вёрстки.

## Возможности

- 👥 **Мультипользовательность**: изоляция данных по `telegram_id`, у каждого свои подписки и история.
- 🔎 **Подписки на поиск**: запрос, регион (популярные + поиск по названию через `/areas`),
  опыт, занятость, вилка зарплаты, «только с зарплатой», стоп-слова.
- 🚫 **Стоп-слова**: если слово встречается в названии или описании — вакансия не показывается.
- ⏱ **Планировщик**: фоновый опрос API каждые N минут (по умолчанию 15), сортировка по
  `publication_time`, только новые с прошлой проверки.
- 🔁 **Дедупликация**: вакансия приходит пользователю ровно один раз (таблица `sent_vacancies`).
- 💱 **Нормализация зарплат**: конвертация в одну валюту (по умолчанию ₽) по курсам из
  `/dictionaries`, кэш курсов на 24 часа.
- 🔔 **Уведомления с кнопками**: «🔥 Откликнуться», «⭐ В избранное», «🚫 Скрыть компанию».
- 📊 **Аналитика**: медианная зарплата, топ-10 навыков, динамика по дням, экспорт в CSV.
- 🐳 **Запуск**: `docker compose up -d --build` или `python -m bot` без Docker.
- ✅ **Тесты**: 54 юнит-теста (клиент API с замоканным httpx, дедупликация, валюты, фильтры, хендлеры, планировщик).

## Стек

Python 3.11+ · aiogram 3.x · httpx (async) · SQLAlchemy 2.0 (async) · aiosqlite ·
APScheduler · pydantic-settings.

БД диалект-агностична: SQLite по умолчанию, для PostgreSQL достаточно поменять `DATABASE_URL`.

## Быстрый старт на сервере (VPS/Linux) одной командой

```bash
# на сервере под root (Ubuntu/Debian):

curl -fsSL https://raw.githubusercontent.com/pashanoob1-commits/hh_pars/cline/cfs4mq4t/hh-parser-bot/deploy.sh -o deploy.sh
bash deploy.sh
```

Скрипт: поставит Docker, скачает код, спросит токен бота и email для User-Agent,
создаст `.env`, соберёт и запустит контейнер с автоперезапуском.

Полезные режимы:

```bash
BOT_TOKEN='123:ABC' HH_USER_AGENT='hh-parser-bot/1.0 (me@example.com)' bash deploy.sh   # без вопросов
SKIP_DOCKER=1 bash deploy.sh      # только подготовить файлы (без установки Docker)
FORCE_ENV=1  bash deploy.sh       # перезаписать существующий .env
```

Если репозиторий приватный, передайте доступ через токен:

```bash
REPO_URL='https://ТОКЕН@github.com/pashanoob1-commits/hh_pars.git' bash deploy.sh
```

## Деплой на GCP e2-micro (Always Free)

Одна бесплатная VM e2-micro (1 ГБ RAM) отлично тянет этого бота. Условия бесплатности:
регион `us-central1` / `us-west1` / `us-east1`, диск — standard persistent disk ≤ 30 ГБ,
трафик на исходящие — 1 ГБ/мес (нашему боту хватает с большим запасом).

1. **Compute Engine → Create instance:** machine type `e2-micro`, boot disk `Ubuntu 24.04 LTS`,
   `30 GB standard persistent disk`, firewall — только SSH.
2. Подключитесь по кнопке **SSH** в консоли (браузерный терминал, ключи не нужны).
3. Установите бота одним из способов:

```bash
# Вариант A: Docker (нужен swap, иначе сборка образа может не уложиться в 1 ГБ RAM)
sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
bash deploy.sh

# Вариант B: без Docker, через systemd (легче для 1 ГБ RAM)
cd hh-parser-bot && sudo bash deploy/systemd/install.sh
```

Управление при установке через systemd:

```bash
sudo journalctl -u hh-parser-bot -f      # логи
sudo systemctl restart hh-parser-bot    # перезапуск
sudo systemctl status hh-parser-bot     # состояние
```

> Диск VM постоянный, поэтому SQLite-база и подписки сохраняются между перезагрузками.
> Включите в GCP Budget alerts — при выходе за лимиты free tier может прийти счёт.

## Деплой на PaaS (Northflank / Railway / Render)

Бот — это фоновый процесс (long polling), входящие порты ему не нужны. На PaaS он
разворачивается как **worker / background service** (без публичного порта и health-check).

**Настройки сервиса:**

| Параметр | Значение |
|---|---|
| Тип сервиса | Worker / Background (не Web) |
| Сборка | Dockerfile из Git |
| Контекст сборки | `hh-parser-bot` (если репозиторий — корень) |
| Путь к Dockerfile | `hh-parser-bot/Dockerfile` |
| Команда запуска | `python -m bot` (уже в образе) |
| Реплики | **ровно 1** (иначе будут дубли уведомлений) |

**Переменные окружения (добавьте как secrets):**

```env
BOT_TOKEN=123456:ABC-DEF...
HH_USER_AGENT=hh-parser-bot/1.0 (you@example.com)
POLL_INTERVAL_MINUTES=15
```

**Хранилище — выберите один вариант:**

1. **Managed PostgreSQL** (рекомендуется для PaaS — нет проблем с правами на volume):
   создайте БД в панели и укажите
   ```env
   DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/dbname
   ```
   Драйвер `asyncpg` уже включён в образ (в `requirements-postgres.txt` — для локального запуска).

2. **Persistent volume** (для SQLite): примонтируйте диск в `/app/data` и укажите
   ```env
   DATABASE_URL=sqlite+aiosqlite:////app/data/bot.db
   LOG_FILE=/app/data/logs/bot.log
   ```
   Бот сам создаст каталоги и, если контейнер стартует от root, отдаст их рабочему
   пользователю и понизит привилегии (`bot/utils/permissions.py`).

> Без persistent volume/БД все подписки и история отправок потеряются при пересоздании контейнера.

## Быстрый старт

### 1. Получите токен бота

1. Откройте в Telegram [@BotFather](https://t.me/BotFather).
2. `/newbot` → задайте имя и username.
3. Скопируйте токен вида `123456:ABC-DEF...`.

### 2. Установка (без Docker)

```bash
cd hh-parser-bot
python3.11 -m venv .venv
source .venv/bin/activate           # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                # и заполните BOT_TOKEN / HH_USER_AGENT
python -m bot
```

### 3. Установка (Docker)

```bash
cd hh-parser-bot
cp .env.example .env                # и заполните BOT_TOKEN / HH_USER_AGENT
docker compose up -d --build
docker compose logs -f bot
```

SQLite-база и логи живут в volume `bot-data` (`/app/data` внутри контейнера).

## Настройка `.env`

| Переменная | По умолчанию | Описание |
|---|---|---|
| `BOT_TOKEN` | — | Токен бота от @BotFather (**обязательно**) |
| `HH_USER_AGENT` | `hh-parser-bot/1.0 (you@example.com)` | Обязателен для hh.ru: `app/version (email)` |
| `HH_API_BASE` | `https://api.hh.ru` | База API |
| `HH_MIN_REQUEST_INTERVAL` | `0.5` | Минимальный интервал между запросами, сек |
| `HH_MAX_RETRIES` | `5` | Число попыток при 429/5xx |
| `HH_PER_PAGE` | `50` | Вакансий за запрос |
| `DATABASE_URL` | `sqlite+aiosqlite:///./data/bot.db` | DSN БД (PostgreSQL: `postgresql+asyncpg://…`) |
| `POLL_INTERVAL_MINUTES` | `15` | Интервал опроса подписок |
| `FIRST_RUN_LIMIT` | `5` | Сколько вакансий прислать при первой проверке подписки |
| `BASE_CURRENCY` | `RUR` | Валюта, в которую нормализуются зарплаты |
| `MAX_SUBSCRIPTIONS_PER_USER` | `10` | Лимит подписок на пользователя |
| `CURRENCY_CACHE_HOURS` | `24` | Время жизни кэша курсов |
| `LOG_LEVEL` | `INFO` | Уровень логирования |
| `LOG_FILE` | `./data/logs/bot.log` | Файл лога (ротация 5 МБ × 5) |

> ⚠️ Токены хранятся только в `.env` (он в `.gitignore`) — не коммитьте их и не
> прописывайте в Dockerfile.

## Команды бота

| Команда | Что делает |
|---|---|
| `/start` | Регистрация и краткая справка |
| `/help` | Список команд |
| `/add` | Мастер создания подписки (8 шагов) |
| `/list` | Мои подписки с кнопками управления |
| `/del <id>` | Удалить подписку (без id — выбор кнопками) |
| `/pause <id>` / `/resume <id>` | Пауза / возобновление |
| `/stopwords <id> [add\|del\|clear] [слова]` | Стоп-слова подписки |
| `/favorites` | Избранные вакансии |
| `/unblock [id]` | Чёрный список компаний |
| `/stats <id>` | Статистика + экспорт в CSV |
| `/cancel` | Отменить текущий диалог |

Примеры:

```text
/add                                  # запустить мастер
/stopwords 1 add 1С, продажи          # добавить стоп-слова в подписку #1
/stopwords 1                          # показать и управлять кнопками
/stats 1                              # медиана, топ навыков, динамика, CSV
```

### Пример уведомления

```text
<b>Python-разработчик (FastAPI)</b>
🏢 ООО Ромашка
💰 180 000 – 250 000 ₽
📍 Москва
🎓 Опыт: От 1 до 3 лет

<i>Опыт коммерческой разработки на Python, знание FastAPI и PostgreSQL...</i>

🔔 Подписка: «python backend» (Москва)

[🔥 Откликнуться] [⭐ В избранное] [🚫 Скрыть компанию]
```

### Мастер `/add`

1. Поисковый запрос → 2. Регион (кнопки популярных + поиск по названию) →
3. Опыт → 4. Занятость → 5–6. Вилка зарплаты → 7. Только с зарплатой? →
8. Стоп-слова → предпросмотр и подтверждение.

## Архитектура

```text
hh-parser-bot/
├── bot/
│   ├── __main__.py          # точка входа: engine, БД, бот, планировщик
│   ├── config.py            # pydantic-settings (.env)
│   ├── hh_api/              # клиент api.hh.ru: вакансии, регионы, словари
│   │   ├── client.py        # rate limit, retry 429/5xx, обработка 403
│   │   └── models.py        # pydantic-модели (HHVacancy, Area, SearchParams)
│   ├── db/
│   │   ├── models.py        # ORM: users, subscriptions, sent_vacancies, ...
│   │   ├── database.py      # async engine, session factory, init_db
│   │   └── repositories.py  # доступ к данным
│   ├── scheduler/
│   │   └── poller.py        # опрос подписок, фильтры, отправка, дедупликация
│   ├── handlers/            # aiogram-роутеры и FSM-мастер подписки
│   ├── services/            # бизнес-логика: подписки, дедуп, валюты, стоп-слова, статистика
│   ├── middlewares/         # сессия БД + прокидывание зависимостей
│   └── utils/               # логирование, работа со временем
├── tests/                   # 54 юнит-теста
├── migrations/              # SQL-скрипт начальной схемы
├── .env.example
├── docker-compose.yml
├── Dockerfile
├── requirements.txt / requirements-dev.txt
└── README.md
```

### Схема БД

| Таблица | Назначение | Ключевые поля |
|---|---|---|
| `users` | Пользователи бота | `telegram_id` (unique) |
| `subscriptions` | Поисковые подписки | `query`, `area_id`, `experience`, `employment`, `salary_min/max`, `only_with_salary`, `stop_words` (JSON), `is_active`, `last_checked_at` |
| `sent_vacancies` | Дедупликация + снимок вакансии | unique (`user_id`, `vacancy_id`), `payload` (JSON) |
| `favorite_vacancies` | Избранное | unique (`user_id`, `vacancy_id`) |
| `blocked_employers` | Чёрный список компаний | unique (`user_id`, `employer_id`) |
| `currencies` | Кэш курсов к RUR | `code`, `rate`, `updated_at` |

Миграции для MVP — `Base.metadata.create_all` при старте (`init_db`).
Тот же DDL в виде SQL-скрипта лежит в `migrations/001_init.sql` (для ручного
применения или перехода на Alembic: модели декларативные и диалект-агностичные).

### Как работает планировщик

1. APScheduler каждые `POLL_INTERVAL_MINUTES` вызывает `VacancyPoller.poll_once()`.
2. Для каждой активной подписки: запрос к `/vacancies` с `order_by=publication_time`.
3. Фильтры: архивные → стоп-слова → чёрный список компаний → верхняя граница вилки →
   watermark `last_checked_at`.
4. Дедупликация по `sent_vacancies` (вакансия приходит ровно один раз).
5. Первая проверка новой подписки присылает не больше `FIRST_RUN_LIMIT` самых свежих вакансий.
6. Зарплата конвертируется в `BASE_CURRENCY`, сообщение уходит с inline-кнопками,
   отправленное фиксируется в `sent_vacancies`.

### Соблюдение правил API hh.ru

- Обязательный `User-Agent` с контактом (валидируется в конфиге).
- Минимальный интервал между запросами (`HH_MIN_REQUEST_INTERVAL`).
- Retry с экспоненциальной задержкой и поддержкой `Retry-After` на 429/5xx.
- Отдельная обработка 403 (`HHForbiddenError`).
- Только официальный API, без HTML-скрапинга.

## Тесты

```bash
pip install -r requirements-dev.txt
pytest -q
```

Покрыто: нормализация ответов API и retry (respx), поиск регионов, курсы валют,
конвертация зарплат, дедупликация, стоп-слова, чёрный список, вилка и watermark,
лимит подписок, команды `/start`, `/help`, `/add`, `/list`, `/stopwords`,
`/favorites`, `/unblock`, кнопки «в избранное» и «скрыть компанию», планировщик.

## Дорожная карта

- [x] MVP: подписки, планировщик, дедупликация, стоп-слова, чёрный список, валюты, CSV-экспорт
- [ ] Alembic-миграции вместо `create_all`
- [ ] Больше источников поиска (несколько запросов на подписку, remote-only)
- [ ] Топ навыков из полных карточек вакансий (`/vacancies/{id}`) — сейчас из снапшотов выдачи
- [ ] Веб-панель администратора
- [ ] Уведомления о «горячих» вакансиях (много откликов, свежая публикация)

**Вне скоупа (осознанно):** автоотклики на вакансии (риск бана аккаунта hh.ru),
платные подписки/монетизация.

## Отличия от проектов-референсов

Подробный разбор — в `../docs/references-summary.md`.

- [HollowWonder/hh-job-tracker](https://github.com/HollowWonder/hh-job-tracker) — берём
  официальный API, нормализованную схему БД, таблицу курсов, разделение слоёв и логирование.
  Отличия: честный `User-Agent` вместо случайного (`fake_useragent` нарушает правила hh.ru),
  async httpx вместо sync, pydantic-settings + `.env` вместо конфига в коде, без pandas.
- [osiriser/hh.ru_parser_telegram_bot](https://github.com/osiriser/hh.ru_parser_telegram_bot) —
  берём управление через чат, inline-кнопки, Docker-развёртывание и CSV-экспорт.
  Отличия: вместо Selenium + BeautifulSoup (потеря ~60% вакансий) — официальный API,
  aiogram 3.x вместо 2.x, мультипользовательность вместо одного CSV, токены в `.env`.

## Лицензия

MIT.

