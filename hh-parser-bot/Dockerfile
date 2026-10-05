FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Сначала зависимости — так слой кэшируется при изменении кода.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Драйвер PostgreSQL (для managed-БД на PaaS: Northflank, Railway, Render...).
# По умолчанию включён; отключить: docker build --build-arg INSTALL_POSTGRES=0 .
ARG INSTALL_POSTGRES=1
RUN if [ "$INSTALL_POSTGRES" = "1" ]; then \
      pip install --no-cache-dir "asyncpg>=0.29"; \
    fi

COPY bot ./bot
COPY pytest.ini ./

# Каталог для SQLite и логов (монтируется volume в docker-compose).
RUN mkdir -p /app/data/logs

# Запуск без root-прав.
RUN useradd --create-home --uid 1000 botuser \
    && chown -R botuser:botuser /app
USER botuser

CMD ["python", "-m", "bot"]
