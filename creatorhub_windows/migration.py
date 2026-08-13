from __future__ import annotations

import json
import shutil
from pathlib import Path

from .paths import RuntimePaths


def migration_candidates() -> list[Path]:
    candidates = [Path(r"D:\recod\CreatorHub"), Path.home() / "CreatorHub"]
    return [item.resolve() for item in candidates
            if (item / "data" / "creatorhub.db").is_file()]


def migrate_from(source: Path, paths: RuntimePaths) -> dict:
    """复制旧数据，绝不删除源目录；调用方负责在服务停止时执行。"""
    source = source.resolve()
    source_db = source / "data" / "creatorhub.db"
    if not source_db.is_file():
        raise FileNotFoundError(f"找不到旧数据库：{source_db}")
    copied = []
    if not paths.database.exists():
        paths.database.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_db, paths.database)
        copied.append(str(paths.database))
    old_config = source / "config.yaml"
    if old_config.is_file() and not paths.config.exists():
        shutil.copy2(old_config, paths.config)
        copied.append(str(paths.config))
    old_wechat = source / "data" / "wechat_oa"
    if old_wechat.is_dir():
        paths.wechat_data.mkdir(parents=True, exist_ok=True)
        for item in old_wechat.iterdir():
            if item.name.lower() == "profiles":
                continue
            target = paths.wechat_data / item.name
            if item.is_dir():
                shutil.copytree(item, target, dirs_exist_ok=True)
            elif not target.exists():
                shutil.copy2(item, target)
        copied.append(str(paths.wechat_data))
        old_oa_profiles = old_wechat / "profiles"
        new_oa_profiles = paths.local_data / "wechat_oa" / "profiles"
        if old_oa_profiles.is_dir():
            shutil.copytree(old_oa_profiles, new_oa_profiles, dirs_exist_ok=True)
            copied.append(str(new_oa_profiles))
    old_profiles = source / "profiles"
    if not old_profiles.is_dir():
        old_profiles = source / "data" / "profiles"
    new_profiles = paths.local_data / "profiles"
    if old_profiles.is_dir():
        shutil.copytree(old_profiles, new_profiles, dirs_exist_ok=True)
        copied.append(str(new_profiles))
    report = {"source": str(source), "copied": copied, "source_preserved": True}
    (paths.program_data / "migration-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report
