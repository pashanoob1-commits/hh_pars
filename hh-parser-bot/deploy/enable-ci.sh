#!/usr/bin/env bash
#
# Включает GitHub Actions для репозитория: копирует готовый workflow
# из deploy/github-actions/ci.yml в .github/workflows/ci.yml.
#
# Запускать из любой папки. Для пуша файла нужен токен с правом `workflow`
# (или добавьте файл через веб-интерфейс GitHub).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SRC="$ROOT/hh-parser-bot/deploy/github-actions/ci.yml"
DST="$ROOT/.github/workflows/ci.yml"

[ -f "$SRC" ] || { echo "Не найден $SRC" >&2; exit 1; }

mkdir -p "$(dirname "$DST")"
cp "$SRC" "$DST"

echo "✅ Workflow скопирован: $DST"
echo "Дальше:"
echo "    git add .github/workflows/ci.yml"
echo "    git commit -m 'ci: enable GitHub Actions'"
echo "    git push"
