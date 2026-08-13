from __future__ import annotations

import argparse
import ctypes
import json
import sys
from pathlib import Path

from .backup import create_backup
from .certificates import ensure_certificate
from .migration import migrate_from, migration_candidates
from .paths import (ensure_directories, prepare_environment, register_operator,
                    runtime_paths)


def _resource_root() -> Path:
    frozen = getattr(sys, "_MEIPASS", "")
    return Path(frozen).resolve() if frozen else Path(__file__).resolve().parents[1]


def _paths():
    return prepare_environment(_resource_root() / "config.example.yaml")


def migrate_auto() -> int:
    paths = runtime_paths()
    ensure_directories(paths)
    register_operator(paths)
    if paths.database.exists():
        return 0
    candidates = migration_candidates()
    if not candidates:
        return 0
    source = candidates[0]
    answer = ctypes.windll.user32.MessageBoxW(
        0,
        f"检测到旧版 CreatorHub 数据：\n{source}\n\n是否复制账号、数据库和浏览器画像？原目录会保留。",
        "CreatorHub 数据迁移", 0x24,
    )
    if answer != 6:
        return 0
    report = migrate_from(source, paths)
    ctypes.windll.user32.MessageBoxW(
        0, "迁移完成，原数据未删除。\n\n" + "\n".join(report["copied"]),
        "CreatorHub 数据迁移", 0x40,
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("server", "tray", "backup", "migrate-auto", "prepare"))
    args = parser.parse_args()
    if args.command == "server":
        from .server import run_server
        return run_server()
    if args.command == "tray":
        from .tray import run_tray
        return run_tray()
    if args.command == "backup":
        print(create_backup(_paths()))
        return 0
    if args.command == "prepare":
        paths = _paths()
        ensure_certificate(paths.certificates)
        return 0
    return migrate_auto()


if __name__ == "__main__":
    raise SystemExit(main())
