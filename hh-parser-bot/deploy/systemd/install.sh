#!/usr/bin/env bash
#
# Установка hh-parser-bot через systemd (без Docker) — для маленьких VM,
# например GCP e2-micro (Always Free, 1 ГБ RAM).
#
# Запускать из папки проекта, от root:
#   cd hh-parser-bot && bash deploy/systemd/install.sh
#
# Проверка без изменения системы (скопировать файлы и поставить зависимости):
#   SKIP_SYSTEMD=1 INSTALL_DIR=/tmp/hh-parser-bot bash deploy/systemd/install.sh
#
set -euo pipefail

INSTALL_DIR="${INSTALL_DIR:-/opt/hh-parser-bot}"
SERVICE_NAME="${SERVICE_NAME:-hh-parser-bot}"
BOT_USER="${BOT_USER:-hhbot}"
SKIP_SYSTEMD="${SKIP_SYSTEMD:-0}"
# Доп. аргументы pip (прокси, свои сертификаты): PIP_ARGS='--cert /path/ca.crt'
PIP_ARGS="${PIP_ARGS:-}"

log()  { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[!]\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31m[x]\033[0m %s\n' "$*" >&2; exit 1; }

[ -f "./bot/__main__.py" ] || die "Запустите скрипт из папки hh-parser-bot"
[ -f "./.env" ] || die "Нет файла .env — скопируйте .env.example в .env и укажите BOT_TOKEN"

if [ "$(id -u)" != "0" ] && [ "$SKIP_SYSTEMD" != "1" ]; then
    die "Нужны права root: sudo bash deploy/systemd/install.sh"
fi

# 1. Системные пакеты для venv
if [ "$SKIP_SYSTEMD" != "1" ]; then
    log "Проверяю python3-venv..."
    if ! python3 -m venv --help >/dev/null 2>&1; then
        if command -v apt-get >/dev/null; then
            apt-get update -qq
            DEBIAN_FRONTEND=noninteractive apt-get install -y python3-venv python3-pip
        elif command -v dnf >/dev/null; then
            dnf install -y python3-pip
        fi
    fi
fi

# 2. Пользователь бота (не root)
if [ "$SKIP_SYSTEMD" != "1" ]; then
    if ! id "$BOT_USER" >/dev/null 2>&1; then
        log "Создаю системного пользователя $BOT_USER"
        useradd --system --create-home --shell /usr/sbin/nologin "$BOT_USER"
    fi
fi

# 3. Копируем код
log "Копирую код в $INSTALL_DIR"
mkdir -p "$INSTALL_DIR"
rm -rf "$INSTALL_DIR/bot" "$INSTALL_DIR/migrations"
cp -r bot "$INSTALL_DIR/"
[ -d migrations ] && cp -r migrations "$INSTALL_DIR/"
cp requirements.txt "$INSTALL_DIR/"
[ -f requirements-postgres.txt ] && cp requirements-postgres.txt "$INSTALL_DIR/"
cp .env "$INSTALL_DIR/.env"
chmod 600 "$INSTALL_DIR/.env"

# 4. Виртуальное окружение
log "Создаю venv и ставлю зависимости (на e2-micro занимает пару минут)"
python3 -m venv "$INSTALL_DIR/.venv"
# shellcheck disable=SC2086 — $PIP_ARGS намеренно разбивается на аргументы
"$INSTALL_DIR/.venv/bin/pip" install $PIP_ARGS --quiet --upgrade pip
"$INSTALL_DIR/.venv/bin/pip" install $PIP_ARGS --quiet -r "$INSTALL_DIR/requirements.txt"

# Опционально драйвер PostgreSQL
if grep -qi '^DATABASE_URL=postgresql' "$INSTALL_DIR/.env" 2>/dev/null; then
    log "Вижу PostgreSQL в DATABASE_URL — ставлю asyncpg"
    "$INSTALL_DIR/.venv/bin/pip" install $PIP_ARGS --quiet "asyncpg>=0.29"
fi

# Каталоги данных и права
mkdir -p "$INSTALL_DIR/data/logs"
if [ "$SKIP_SYSTEMD" != "1" ]; then
    chown -R "$BOT_USER:$BOT_USER" "$INSTALL_DIR"
fi

# 5. systemd-юнит
if [ "$SKIP_SYSTEMD" != "1" ]; then
    UNIT_SRC="./deploy/systemd/${SERVICE_NAME}.service"
    [ -f "$UNIT_SRC" ] || die "Не найден $UNIT_SRC"
    UNIT_DST="/etc/systemd/system/${SERVICE_NAME}.service"
    log "Устанавливаю unit $UNIT_DST"
    sed -e "s|/opt/hh-parser-bot|$INSTALL_DIR|g" \
        -e "s|^User=.*|User=$BOT_USER|" \
        -e "s|^Group=.*|Group=$BOT_USER|" \
        "$UNIT_SRC" > "$UNIT_DST"

    systemctl daemon-reload
    systemctl enable --now "$SERVICE_NAME"
    sleep 3
    systemctl --no-pager --full status "$SERVICE_NAME" | head -20 || true
    echo
    log "Готово! Откройте бота в Telegram и отправьте /start"
    echo "    Логи:       journalctl -u $SERVICE_NAME -f"
    echo "    Перезапуск: systemctl restart $SERVICE_NAME"
    echo "    Остановка:  systemctl stop $SERVICE_NAME"
    echo "    Обновление: cp -r bot $INSTALL_DIR/ && systemctl restart $SERVICE_NAME"
else
    warn "SKIP_SYSTEMD=1 — юнит не установлен"
    log "Код и зависимости готовы в $INSTALL_DIR"
    echo "    Проверка запуска: $INSTALL_DIR/.venv/bin/python -m bot"
fi
