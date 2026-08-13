from __future__ import annotations

import hashlib
import hmac
import html
import ipaddress
import json
import os
import secrets
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse


COOKIE_NAME = "creatorhub_session"
SESSION_SECONDS = 12 * 60 * 60


def _load(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save(path: Path, payload: dict) -> None:
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temp, path)


def _derive(password: str, salt_hex: str) -> str:
    salt = bytes.fromhex(salt_hex)
    return hashlib.scrypt(password.encode("utf-8"), salt=salt,
                          n=2**15, r=8, p=1, dklen=32,
                          maxmem=64 * 1024 * 1024).hex()


def _is_loopback(host: str | None) -> bool:
    try:
        return ipaddress.ip_address(host or "").is_loopback
    except ValueError:
        return False


def _session_token(secret: str, expires: int) -> str:
    message = str(expires)
    signature = hmac.new(bytes.fromhex(secret), message.encode(), hashlib.sha256).hexdigest()
    return f"{message}.{signature}"


def _valid_session(secret: str, token: str) -> bool:
    try:
        expires_text, signature = token.split(".", 1)
        if int(expires_text) < int(time.time()):
            return False
        expected = _session_token(secret, int(expires_text)).split(".", 1)[1]
        return hmac.compare_digest(signature, expected)
    except (ValueError, TypeError):
        return False


def _page(title: str, body: str) -> HTMLResponse:
    return HTMLResponse(f"""<!doctype html><html lang="zh-CN"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)} · CreatorHub</title>
<style>body{{font:15px system-ui;background:#f4f6f8;color:#18202a;margin:0}}
main{{max-width:420px;margin:8vh auto;background:#fff;padding:28px;border-radius:16px;box-shadow:0 12px 40px #10203020}}
input,button{{box-sizing:border-box;width:100%;padding:12px;margin:7px 0;border-radius:9px;border:1px solid #ccd3dc}}
button{{background:#07c160;color:#fff;border:0;font-weight:700}}p{{color:#687383}}.error{{color:#c62828}}</style></head>
<body><main><h1>{html.escape(title)}</h1>{body}</main></body></html>""")


def install_security(app: FastAPI, security_path: Path) -> None:
    public_paths = {"/windows/login", "/windows/setup", "/windows/setup/status"}

    @app.middleware("http")
    async def require_login(request: Request, call_next):
        if request.url.path in public_paths:
            return await call_next(request)
        state = _load(security_path)
        if not state.get("password_hash"):
            if _is_loopback(request.client.host if request.client else None):
                return RedirectResponse("/windows/setup", status_code=303)
            return JSONResponse({"detail": "请先在安装电脑上完成管理员初始化"}, 503)
        local_token = request.headers.get("X-CreatorHub-Local", "")
        if local_token and hmac.compare_digest(local_token, state.get("local_token", "")):
            return await call_next(request)
        token = request.cookies.get(COOKIE_NAME, "")
        if _valid_session(state.get("session_secret", ""), token):
            return await call_next(request)
        if request.url.path.startswith("/api/") or request.url.path == "/health":
            return JSONResponse({"detail": "需要管理员登录"}, 401)
        return RedirectResponse("/windows/login", status_code=303)

    @app.get("/windows/setup/status")
    async def setup_status():
        return {"configured": bool(_load(security_path).get("password_hash"))}

    @app.get("/windows/setup")
    async def setup_page(request: Request):
        if not _is_loopback(request.client.host if request.client else None):
            raise HTTPException(403, "管理员初始化只能在安装电脑上完成")
        if _load(security_path).get("password_hash"):
            return RedirectResponse("/windows/login", status_code=303)
        return _page("创建管理员密码", """
<p>首次启动必须在本机创建管理员密码，完成后才开放局域网访问。</p>
<form method="post"><input name="password" type="password" minlength="10" required placeholder="至少10位密码">
<input name="confirm" type="password" minlength="10" required placeholder="再次输入密码">
<button>保存并进入 CreatorHub</button></form>""")

    @app.post("/windows/setup")
    async def setup_submit(request: Request):
        if not _is_loopback(request.client.host if request.client else None):
            raise HTTPException(403, "管理员初始化只能在安装电脑上完成")
        form = await request.form()
        password = str(form.get("password") or "")
        if len(password) < 10 or password != str(form.get("confirm") or ""):
            return _page("创建管理员密码", '<p class="error">密码至少10位，且两次输入必须一致。</p>')
        salt = secrets.token_hex(16)
        state = {
            "salt": salt,
            "password_hash": _derive(password, salt),
            "session_secret": secrets.token_hex(32),
            "local_token": secrets.token_urlsafe(32),
        }
        _save(security_path, state)
        expires = int(time.time()) + SESSION_SECONDS
        response = RedirectResponse("/", status_code=303)
        response.set_cookie(COOKIE_NAME, _session_token(state["session_secret"], expires),
                            max_age=SESSION_SECONDS, secure=True, httponly=True,
                            samesite="strict")
        return response

    @app.get("/windows/login")
    async def login_page():
        if not _load(security_path).get("password_hash"):
            return RedirectResponse("/windows/setup", status_code=303)
        return _page("管理员登录", """
<form method="post"><input name="password" type="password" required placeholder="管理员密码">
<button>登录</button></form>""")

    @app.post("/windows/login")
    async def login_submit(request: Request):
        form = await request.form()
        password = str(form.get("password") or "")
        state = _load(security_path)
        actual = _derive(password, state.get("salt", "")) if state.get("salt") else ""
        if not hmac.compare_digest(actual, state.get("password_hash", "")):
            return _page("管理员登录", '<p class="error">密码错误。</p>')
        expires = int(time.time()) + SESSION_SECONDS
        response = RedirectResponse("/", status_code=303)
        response.set_cookie(COOKIE_NAME, _session_token(state["session_secret"], expires),
                            max_age=SESSION_SECONDS, secure=True, httponly=True,
                            samesite="strict")
        return response

    @app.post("/windows/logout")
    async def logout():
        response = RedirectResponse("/windows/login", status_code=303)
        response.delete_cookie(COOKIE_NAME)
        return response
