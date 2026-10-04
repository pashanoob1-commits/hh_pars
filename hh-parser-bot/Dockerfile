FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Сначала зависимости — так слой кэшируется при изменении кода.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot ./bot
COPY pytest.ini ./

# Каталог для SQLite и логов (монтируется volume в docker-compose).
RUN mkdir -p /app/data/logs

# Запуск без root-прав.
RUN useradd --create-home --uid 1000 botuser \
    && chown -R botuser:botuser /app
USER botuser

CMD ["python", "-m", "bot"]
