from __future__ import annotations

import asyncio
import io
import json
import os
import shutil
import sqlite3
import tempfile
import zipfile
from datetime import datetime, timedelta
from pathlib import Path

from cryptography.fernet import Fernet

from .paths import RuntimePaths


def _backup_sqlite(source: Path, target: Path) -> None:
    if not source.exists():
        return
    source_db = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
    target_db = sqlite3.connect(target)
    try:
        source_db.backup(target_db)
    finally:
        target_db.close()
        source_db.close()


def _backup_key(paths: RuntimePaths) -> bytes:
    key_path = paths.program_data / ".backup.key"
    if not key_path.exists():
        key_path.write_bytes(Fernet.generate_key())
    return key_path.read_bytes().strip()


def create_backup(paths: RuntimePaths) -> Path:
    paths.backups.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    output = paths.backups / f"CreatorHub-{stamp}.chbackup"
    with tempfile.TemporaryDirectory(prefix="creatorhub-backup-") as value:
        temp = Path(value)
        _backup_sqlite(paths.database, temp / "creatorhub.db")
        _backup_sqlite(paths.wechat_data / "wechat_oa.db", temp / "wechat_oa.db")
        for source, name in (
            (paths.config, "config.yaml"),
            (paths.wechat_data / ".creatorhub-wechat.key", "wechat.key"),
            (paths.security, "security.json"),
            (paths.operator, "operator.json"),
        ):
            if source.exists():
                shutil.copy2(source, temp / name)
        manifest = {
            "product": "CreatorHub", "created_at": datetime.now().isoformat(),
            "format": 1, "contains_browser_profiles": False,
        }
        (temp / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            for item in temp.iterdir():
                archive.write(item, item.name)
        output.write_bytes(Fernet(_backup_key(paths)).encrypt(buffer.getvalue()))
    prune_backups(paths, keep_days=14)
    return output


def prune_backups(paths: RuntimePaths, keep_days: int = 14) -> int:
    cutoff = datetime.now() - timedelta(days=keep_days)
    removed = 0
    for item in paths.backups.glob("CreatorHub-*.chbackup"):
        if datetime.fromtimestamp(item.stat().st_mtime) < cutoff:
            item.unlink(missing_ok=True)
            removed += 1
    return removed


async def daily_backup_loop(paths: RuntimePaths) -> None:
    while True:
        now = datetime.now()
        next_run = (now + timedelta(days=1)).replace(hour=3, minute=10,
                                                        second=0, microsecond=0)
        await asyncio.sleep(max(60, (next_run - now).total_seconds()))
        try:
            await asyncio.to_thread(create_backup, paths)
        except Exception as exc:
            paths.logs.mkdir(parents=True, exist_ok=True)
            with (paths.logs / "backup-error.log").open("a", encoding="utf-8") as handle:
                handle.write(f"{datetime.now().isoformat()} {exc!r}\n")
