from __future__ import annotations

import json
import hashlib
import hmac
import os
import re
import tempfile
import urllib.request
from pathlib import Path

import win32cred

from . import PRODUCT_VERSION


REPOSITORY = "gmlgaobo/creatorhub-wechat-oa"
CREDENTIAL_TARGET = "CreatorHub/GitHubReleaseToken"


def save_token(token: str) -> None:
    value = token.strip()
    if not value:
        raise ValueError("令牌不能为空")
    win32cred.CredWrite({
        "Type": win32cred.CRED_TYPE_GENERIC,
        "TargetName": CREDENTIAL_TARGET,
        "CredentialBlob": value.encode("utf-16-le"),
        "Persist": win32cred.CRED_PERSIST_LOCAL_MACHINE,
        "UserName": "github-release",
    }, 0)


def load_token() -> str:
    try:
        item = win32cred.CredRead(CREDENTIAL_TARGET,
                                  win32cred.CRED_TYPE_GENERIC, 0)
        blob = item.get("CredentialBlob") or b""
        return blob.decode("utf-16-le") if isinstance(blob, bytes) else str(blob)
    except Exception:
        return ""


def latest_release() -> dict:
    token = load_token()
    if not token:
        raise RuntimeError("尚未配置 GitHub 私有发布只读令牌")
    request = urllib.request.Request(
        f"https://api.github.com/repos/{REPOSITORY}/releases/latest",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": f"CreatorHub/{PRODUCT_VERSION}",
        },
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        payload = json.loads(response.read().decode("utf-8"))
    tag = str(payload.get("tag_name") or "").lstrip("v")
    assets = [
        {"name": item.get("name"), "size": item.get("size"),
         "url": item.get("browser_download_url"),
         "api_url": item.get("url"), "digest": item.get("digest")}
        for item in payload.get("assets") or []
    ]
    return {
        "current_version": PRODUCT_VERSION, "latest_version": tag,
        "update_available": bool(tag and tag != PRODUCT_VERSION),
        "release_url": payload.get("html_url"), "assets": assets,
    }


def stage_latest_installer(directory: Path) -> dict:
    release = latest_release()
    candidates = [item for item in release["assets"]
                  if re.fullmatch(r"CreatorHub-Setup-.*-x64\.exe",
                                  str(item.get("name") or ""), re.IGNORECASE)]
    if not candidates:
        raise RuntimeError("最新发布中没有 Windows x64 安装程序")
    asset = candidates[0]
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / Path(str(asset["name"])).name
    request = urllib.request.Request(
        str(asset["api_url"]),
        headers={
            "Accept": "application/octet-stream",
            "Authorization": f"Bearer {load_token()}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": f"CreatorHub/{PRODUCT_VERSION}",
        },
    )
    fd, temporary = tempfile.mkstemp(prefix="creatorhub-update-", suffix=".exe",
                                     dir=directory)
    os.close(fd)
    temp_path = Path(temporary)
    try:
        with (
            urllib.request.urlopen(request, timeout=120) as response,
            temp_path.open("wb") as output,
        ):
            while block := response.read(1024 * 1024):
                output.write(block)
        expected_size = int(asset.get("size") or 0)
        if expected_size and temp_path.stat().st_size != expected_size:
            raise RuntimeError("更新安装程序下载不完整")
        digest = str(asset.get("digest") or "")
        if digest.startswith("sha256:"):
            with temp_path.open("rb") as input_file:
                actual = hashlib.file_digest(input_file, "sha256").hexdigest()
            if not hmac.compare_digest(actual, digest.split(":", 1)[1]):
                raise RuntimeError("更新安装程序校验失败")
        os.replace(temp_path, target)
    finally:
        temp_path.unlink(missing_ok=True)
    return {"path": str(target), "release": release}
