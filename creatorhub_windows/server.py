from __future__ import annotations

import asyncio
import json
import os
import sys
import urllib.request
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse

from . import LAN_PORT, PRODUCT_VERSION
from .backup import daily_backup_loop
from .agent_proxy import install_agent_proxy
from .certificates import ensure_certificate, local_ipv4_addresses
from .paths import prepare_environment
from .security import install_security
from .updates import latest_release, load_token, save_token, stage_latest_installer


def _resource_root() -> Path:
    frozen = getattr(sys, "_MEIPASS", "")
    return Path(frozen).resolve() if frozen else Path(__file__).resolve().parents[1]


RESOURCE_ROOT = _resource_root()
if getattr(sys, "frozen", False):
    os.environ.setdefault("CREATORHUB_NODE_DIR", str(Path(sys.executable).parent / "vendor" / "node"))
PATHS = prepare_environment(RESOURCE_ROOT / "config.example.yaml")

from creatorhub_plus import app  # noqa: E402

install_agent_proxy(app, PATHS.security)
install_security(app, PATHS.security)
_original_lifespan = app.router.lifespan_context


@asynccontextmanager
async def _windows_lifespan(application):
    async with _original_lifespan(application):
        task = asyncio.create_task(daily_backup_loop(PATHS))
        try:
            yield
        finally:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass


app.router.lifespan_context = _windows_lifespan


@app.get("/windows/runtime")
async def windows_runtime():
    _cert, _key, fingerprint = ensure_certificate(PATHS.certificates)
    return {
        "product": "CreatorHub", "version": PRODUCT_VERSION,
        "port": LAN_PORT, "addresses": local_ipv4_addresses(),
        "certificate_fingerprint": fingerprint,
    }


@app.get("/windows/update", response_class=HTMLResponse)
async def update_settings():
    configured = "已配置" if load_token() else "未配置"
    return HTMLResponse(f"""<!doctype html><meta charset="utf-8"><title>CreatorHub 更新</title>
<style>body{{font:15px system-ui;max-width:620px;margin:8vh auto}}input,button{{padding:10px;margin:6px;width:100%;box-sizing:border-box}}</style>
<h1>内部版本更新</h1><p>当前版本：{PRODUCT_VERSION} · GitHub 令牌：{configured}</p>
<form method="post"><input type="password" name="token" required placeholder="只读 GitHub Token">
<button>保存到 Windows 凭据管理器</button></form>
<form method="post" action="/windows/update/install">
<button>检查、下载并确认安装最新版本</button></form>
<p><a href="/windows/update/check">只检查版本</a> · <a href="/">返回 CreatorHub</a></p>""")


@app.post("/windows/update")
async def update_token(request: Request):
    form = await request.form()
    save_token(str(form.get("token") or ""))
    return RedirectResponse("/windows/update", status_code=303)


@app.get("/windows/update/check")
async def check_update():
    return await asyncio.to_thread(latest_release)


@app.post("/windows/update/install", response_class=HTMLResponse)
async def install_latest_update():
    staged = await asyncio.to_thread(
        stage_latest_installer, PATHS.program_data / "updates")
    state = json.loads(PATHS.security.read_text(encoding="utf-8"))
    payload = json.dumps({"path": staged["path"]}).encode("utf-8")
    request = urllib.request.Request(
        "http://127.0.0.1:18765/windows/agent/install-update",
        data=payload, method="POST",
        headers={"Content-Type": "application/json",
                 "X-CreatorHub-Local": state["local_token"]},
    )
    def notify_agent():
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.read()
    try:
        await asyncio.to_thread(notify_agent)
    except Exception as exc:
        raise RuntimeError("更新已下载，但托盘代理未运行，无法显示安装确认窗口") from exc
    return HTMLResponse("""<!doctype html><meta charset="utf-8"><h1>更新安装程序已启动</h1>
<p>请在安装电脑上确认 Windows 提示并完成安装。</p><p><a href="/">返回 CreatorHub</a></p>""")


def create_server() -> uvicorn.Server:
    cert, key, _fingerprint = ensure_certificate(PATHS.certificates)
    config = uvicorn.Config(
        app, host="0.0.0.0", port=LAN_PORT,
        ssl_certfile=str(cert), ssl_keyfile=str(key),
        log_level="info", access_log=True, log_config=None,
    )
    return uvicorn.Server(config)


def run_server() -> int:
    server = create_server()
    asyncio.run(server.serve())
    return 0 if server.started else 1
