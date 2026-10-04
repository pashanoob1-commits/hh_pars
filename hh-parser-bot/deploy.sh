#!/usr/bin/env bash
#
# Установка hh-parser-bot на Linux/VPS одной командой.
#
# Что делает:
#   1) ставит Docker (если его нет);
#   2) скачивает код бота из репозитория;
#   3) спрашивает токен бота и email для User-Agent, создаёт .env;
#   4) собирает и запускает контейнер с автоперезапуском.
#
# Использование (на сервере):
#   bash deploy.sh
#
# Неинтерактивно (для автоматизации):
#   BOT_TOKEN='123:ABC' HH_USER_AGENT='hh-parser-bot/1.0 (me@example.com)' bash deploy.sh
#
# Только подготовить файлы, без запуска Docker (для проверки):
#   SKIP_DOCKER=1 bash deploy.sh
#
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/pashanoob1-commits/hh_pars.git}"
BRANCH="${BRANCH:-cline/cfs4mq4t}"
SUBDIR="${SUBDIR:-hh-parser-bot}"
WORKDIR="${WORKDIR:-$HOME/hh-parser-bot}"

log()  { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[!]\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31m[x]\033[0m %s\n' "$*" >&2; exit 1; }

need_cmd() { command -v "$1" >/dev/null 2>&1; }

install_docker() {
    if need_cmd docker; then
        log "Docker уже установлен: $(docker --version)"
    else
        log "Устанавливаю Docker (может занять пару минут)..."
        curl -fsSL https://get.docker.com -o /tmp/get-docker.sh
        sh /tmp/get-docker.sh
        rm -f /tmp/get-docker.sh
    fi

    if ! docker compose version >/dev/null 2>&1; then
        log "Устанавливаю плагин docker compose..."
        if need_cmd apt-get; then
            apt-get update -qq && apt-get install -y docker-compose-plugin
        elif need_cmd dnf; then
            dnf install -y docker-compose-plugin
        else
            die "Не удалось поставить docker compose автоматически — поставьте вручную."
        fi
    fi
    log "docker compose готов"
}

fetch_code() {
    if [ -f "./docker-compose.yml" ] && [ -d "./bot" ]; then
        WORKDIR="$(pwd)"
        log "Использую код из текущей папки: $WORKDIR"
        return
    fi

    if [ -d "$WORKDIR/.git" ]; then
        log "Обновляю код в $WORKDIR"
        git -C "$WORKDIR" fetch --depth 1 origin "$BRANCH"
        git -C "$WORKDIR" checkout "$BRANCH"
        git -C "$WORKDIR" pull --ff-only origin "$BRANCH" || true
        return
    fi

    log "Скачиваю код: $REPO_URL (ветка $BRANCH)"
    rm -rf "$WORKDIR"
    if ! git clone --depth 1 --branch "$BRANCH" "$REPO_URL" "$WORKDIR" 2>/dev/null; then
        warn "Клонирование не удалось (репозиторий приватный — нужен доступ)."
        echo "  Вариант 1: сделать репозиторий публичным (GitHub → Settings → General →"
        echo "             Change repository visibility)."
        echo "  Вариант 2: создать токен (GitHub → Settings → Developer settings →"
        echo "             Personal access tokens) и запустить:"
        echo "             REPO_URL='https://ТОКЕН@github.com/pashanoob1-commits/hh_pars.git' bash deploy.sh"
        echo "  Вариант 3: установить gh и войти: apt-get install -y gh && gh auth login"
        die "Не удалось получить код."
    fi
    WORKDIR="$WORKDIR/$SUBDIR"
    log "Код скачан в $WORKDIR"
}

ask() { # ask <переменная> <подсказка> [значение по умолчанию]
    local __var="$1" __prompt="$2" __current="${3:-}"
    local __value=""
    if [ -n "$__current" ]; then
        printf '%s [%s]: ' "$__prompt" "$__current"
    else
        printf '%s: ' "$__prompt"
    fi
    read -r __value || true
    [ -z "$__value" ] && __value="$__current"
    printf -v "$__var" '%s' "$__value"
}

setup_env() {
    cd "$WORKDIR"
    [ -f ".env.example" ] || die "Не найден .env.example — код скачан не полностью."

    if [ -f ".env" ] && [ -s ".env" ] && [ "${FORCE_ENV:-0}" != "1" ]; then
        log ".env уже существует — оставляю как есть (перезапись: FORCE_ENV=1 bash deploy.sh)"
        return
    fi

    local token="${BOT_TOKEN:-}"
    local agent="${HH_USER_AGENT:-}"

    if [ -z "$token" ]; then
        echo
        echo "Нужен токен бота. Получить: Telegram → @BotFather → /newbot"
        ask token "Вставьте токен бота" ""
    fi
    # Проверяем токен сразу — до остальных вопросов.
    case "$token" in
        *:*) ;;
        *) die "Токен выглядит неправильно: ожидается формат 123456:ABC-DEF..." ;;
    esac

    if [ -z "$agent" ]; then
        local email
        ask email "Email для User-Agent (требование hh.ru)" "user@example.com"
        agent="hh-parser-bot/1.0 ($email)"
    fi

    local tmp
    tmp="$(mktemp)"
    sed -e "s|^BOT_TOKEN=.*|BOT_TOKEN=$token|" \
        -e "s|^HH_USER_AGENT=.*|HH_USER_AGENT=$agent|" \
        .env.example > "$tmp"
    mv "$tmp" .env
    chmod 600 .env
    log ".env создан (права 600 — читать может только ваш пользователь)"
}

start_bot() {
    cd "$WORKDIR"
    log "Собираю и запускаю контейнер..."
    docker compose up -d --build
    sleep 5
    docker compose ps || true
    echo
    log "Последние строки лога:"
    docker compose logs --tail=20 bot || true
    echo
    log "Готово! Откройте своего бота в Telegram и отправьте /start"
    echo "    Логи:        cd $WORKDIR && docker compose logs -f bot"
    echo "    Перезапуск:  cd $WORKDIR && docker compose restart"
    echo "    Обновление:  cd $WORKDIR && git pull && docker compose up -d --build"
    echo "    Остановка:   cd $WORKDIR && docker compose down"
}

main() {
    echo "=== Установка hh-parser-bot ==="
    if [ "${SKIP_DOCKER:-0}" != "1" ]; then
        install_docker
    else
        warn "SKIP_DOCKER=1 — Docker не устанавливаю и не запускаю"
    fi

    fetch_code
    setup_env

    if [ "${SKIP_DOCKER:-0}" != "1" ]; then
        start_bot
    else
        log "Файлы готовы: $WORKDIR"
        echo "    Запуск вручную: cd $WORKDIR && docker compose up -d --build"
    fi
}

main "$@"
