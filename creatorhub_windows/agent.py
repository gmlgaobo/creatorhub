from __future__ import annotations

import asyncio
import hmac
import os
import subprocess
import threading
from pathlib import Path

import uvicorn
from fastapi import Request
from fastapi.responses import JSONResponse

from .paths import prepare_environment
from .security import _load


AGENT_HOST = "127.0.0.1"
AGENT_PORT = 18765


def _resource_root() -> Path:
    import sys

    frozen = getattr(sys, "_MEIPASS", "")
    return Path(frozen).resolve() if frozen else Path(__file__).resolve().parents[1]


def create_agent_server() -> uvicorn.Server:
    os.environ["CREATORHUB_DESKTOP_AGENT"] = "1"
    paths = prepare_environment(_resource_root() / "config.example.yaml")

    # Import only after setting the desktop-agent flag. The core lifespan then
    # starts its BrowserManager without starting a second monitoring engine.
    from creatorhub_plus import app

    @app.post("/windows/agent/install-update")
    async def install_update(request: Request):
        payload = await request.json()
        update_root = (paths.program_data / "updates").resolve()
        installer = Path(str(payload.get("path") or "")).resolve()
        if installer.parent != update_root or not installer.is_file() or installer.suffix.lower() != ".exe":
            return JSONResponse({"detail": "invalid staged installer"}, 400)
        subprocess.Popen([str(installer)], close_fds=True)
        return {"ok": True}

    @app.middleware("http")
    async def local_agent_auth(request: Request, call_next):
        state = _load(paths.security)
        supplied = request.headers.get("X-CreatorHub-Local", "")
        expected = str(state.get("local_token") or "")
        if not expected or not supplied or not hmac.compare_digest(supplied, expected):
            return JSONResponse({"detail": "desktop agent authentication failed"}, 403)
        return await call_next(request)

    return uvicorn.Server(uvicorn.Config(
        app, host=AGENT_HOST, port=AGENT_PORT,
        log_level="warning", access_log=False, log_config=None,
    ))


def start_agent_thread() -> tuple[uvicorn.Server, threading.Thread]:
    server = create_agent_server()
    thread = threading.Thread(
        target=lambda: asyncio.run(server.serve()),
        name="CreatorHubDesktopAgent", daemon=True,
    )
    thread.start()
    return server, thread
