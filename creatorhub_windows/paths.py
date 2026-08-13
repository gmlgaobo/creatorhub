from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

import yaml

from . import LAN_PORT


@dataclass(frozen=True)
class RuntimePaths:
    program_data: Path
    local_data: Path
    config: Path
    database: Path
    wechat_data: Path
    logs: Path
    backups: Path
    certificates: Path
    security: Path
    operator: Path


def runtime_paths() -> RuntimePaths:
    program_root = Path(os.getenv(
        "CREATORHUB_PROGRAM_DATA",
        str(Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData")) / "CreatorHub"),
    )).resolve()
    local_root = Path(os.getenv(
        "CREATORHUB_LOCAL_DATA",
        str(Path(os.environ.get("LOCALAPPDATA", program_root / "operator")) / "CreatorHub"),
    )).resolve()
    return RuntimePaths(
        program_data=program_root,
        local_data=local_root,
        config=program_root / "config.yaml",
        database=program_root / "data" / "creatorhub.db",
        wechat_data=program_root / "data" / "wechat_oa",
        logs=program_root / "logs",
        backups=program_root / "backups",
        certificates=program_root / "certificates",
        security=program_root / "security.json",
        operator=program_root / "operator.json",
    )


def ensure_directories(paths: RuntimePaths) -> None:
    for item in (
        paths.program_data, paths.local_data, paths.database.parent,
        paths.wechat_data, paths.logs, paths.backups, paths.certificates,
        paths.local_data / "profiles", paths.local_data / "wechat_oa" / "profiles",
    ):
        item.mkdir(parents=True, exist_ok=True)


def register_operator(paths: RuntimePaths) -> None:
    payload = {
        "username": os.environ.get("USERNAME", ""),
        "local_data": str(paths.local_data),
    }
    paths.operator.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                              encoding="utf-8")


def ensure_config(paths: RuntimePaths, template: Path) -> None:
    source = paths.config if paths.config.exists() else template
    raw = yaml.safe_load(source.read_text(encoding="utf-8")) or {}
    raw.setdefault("server", {})["host"] = "0.0.0.0"
    raw["server"]["port"] = LAN_PORT
    raw.setdefault("storage", {})["db_path"] = str(paths.database)
    engine = raw.setdefault("engine", {})
    engine["media_dir"] = str(paths.program_data / "data" / "media")
    engine["profiles_dir"] = str(paths.local_data / "profiles")
    engine["xhs_browser_mode"] = "auto"
    paths.config.write_text(
        yaml.safe_dump(raw, allow_unicode=True, sort_keys=False), encoding="utf-8")


def prepare_environment(template: Path) -> RuntimePaths:
    paths = runtime_paths()
    ensure_directories(paths)
    register_operator(paths)
    ensure_config(paths, template)
    os.environ["CREATORHUB_CONFIG_PATH"] = str(paths.config)
    os.environ["CREATORHUB_WECHAT_OA_DATA"] = str(paths.wechat_data)
    os.environ["CREATORHUB_WECHAT_OA_PROFILES"] = str(
        paths.local_data / "wechat_oa" / "profiles")
    os.environ["CREATORHUB_WINDOWS"] = "1"
    node_value = os.getenv("CREATORHUB_NODE_DIR", "").strip()
    node_dir = Path(node_value) if node_value else None
    if node_dir is not None and node_dir.is_dir():
        os.environ["PATH"] = str(node_dir) + os.pathsep + os.environ.get("PATH", "")
    return paths
