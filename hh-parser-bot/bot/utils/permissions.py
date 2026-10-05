"""Права на каталог данных (для контейнеров и PaaS-платформ).

В Kubernetes/Northflank смонтированный volume часто принадлежит root, а бот в
образе запускается от непривилегированного пользователя. Если процесс стартует
от root, этот модуль создаёт каталоги, отдаёт их рабочему пользователю и
понижает привилегии — так бот работает и с volume, и без него.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from bot.config import Settings

logger = logging.getLogger(__name__)

DEFAULT_UID = 1000
DEFAULT_GID = 1000


def _sqlite_path(settings: Settings) -> Path | None:
    if not settings.is_sqlite or "///" not in settings.database_url:
        return None
    raw = settings.database_url.split("///", 1)[1]
    if not raw or raw == ":memory:":
        return None
    return Path(raw).expanduser().resolve()


def data_directories(settings: Settings) -> list[Path]:
    """Каталоги, которые боту нужно уметь создавать и писать."""
    dirs: list[Path] = []

    db_path = _sqlite_path(settings)
    if db_path is not None:
        dirs.append(db_path.parent)

    if settings.log_file:
        dirs.append(Path(settings.log_file).expanduser().resolve().parent)

    # Уникальные пути, сохраняя порядок.
    unique: list[Path] = []
    for directory in dirs:
        if directory not in unique:
            unique.append(directory)
    return unique


def _chown_tree(path: Path, uid: int, gid: int) -> None:
    for root, dirnames, filenames in os.walk(path):
        os.chown(root, uid, gid)
        for name in dirnames + filenames:
            try:
                os.chown(Path(root) / name, uid, gid)
            except OSError:
                # Отдельные файлы могут быть недоступны — это не критично.
                continue


def apply_data_permissions(settings: Settings) -> None:
    """Создаёт каталоги данных; если запущены от root — отдаёт их боту и снимает root."""
    uid = int(os.getenv("APP_UID", str(DEFAULT_UID)))
    gid = int(os.getenv("APP_GID", str(DEFAULT_GID)))

    for directory in data_directories(settings):
        try:
            directory.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            logger.warning("Не удалось создать каталог %s: %s", directory, exc)
            continue
        if os.geteuid() == 0:
            _chown_tree(directory, uid, gid)

    if os.geteuid() != 0:
        return

    # Понижаем привилегии: дальше бот работает как непривилегированный пользователь.
    try:
        os.setgid(gid)
        os.setuid(uid)
        logger.info("Привилегии понижены до uid=%s gid=%s", uid, gid)
    except OSError as exc:
        logger.warning("Не удалось понизить привилегии: %s", exc)
