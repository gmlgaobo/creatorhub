from __future__ import annotations

import asyncio
import json
import re
import urllib.error
import urllib.request

from fastapi import Request
from fastapi.responses import JSONResponse, Response

from .agent import AGENT_HOST, AGENT_PORT
from .security import _is_loopback, _load


_VISIBLE_ROUTES = (
    re.compile(r"^/api/login/(?:browser|creator|xhs|xhs-creator|kuaishou|kuaishou-creator|shipinhao)/start$"),
    re.compile(r"^/api/login/browser/poll$"),
    re.compile(r"^/api/accounts/\d+/(?:relogin/start|open-browser)$"),
    re.compile(r"^/api/login/wechat-oa/start$"),
    re.compile(r"^/api/wechat-oa/login/poll$"),
    re.compile(r"^/api/wechat-oa/accounts/\d+/(?:open-browser|browser-health|close-browser)$"),
)


def is_visible_browser_route(path: str) -> bool:
    return any(pattern.match(path) for pattern in _VISIBLE_ROUTES)


def _forward_sync(request: Request, body: bytes, token: str,
                  requested_from_remote: bool = False) -> Response:
    target = f"http://{AGENT_HOST}:{AGENT_PORT}{request.url.path}"
    if request.url.query:
        target += "?" + request.url.query
    headers = {
        "X-CreatorHub-Local": token,
        "Content-Type": request.headers.get("content-type", "application/json"),
    }
    outbound = urllib.request.Request(
        target, data=body if body else None, headers=headers,
        method=request.method,
    )
    try:
        with urllib.request.urlopen(outbound, timeout=8) as result:
            payload = result.read()
            if result.headers.get_content_type() == "application/json":
                try:
                    decoded = json.loads(payload)
                    if isinstance(decoded, dict):
                        decoded["desktop_execution"] = "installation_host"
                        decoded["requested_from_remote"] = requested_from_remote
                        payload = json.dumps(
                            decoded, ensure_ascii=False).encode("utf-8")
                except (TypeError, ValueError):
                    pass
            return Response(payload, status_code=result.status,
                            media_type=result.headers.get_content_type())
    except urllib.error.HTTPError as error:
        return Response(error.read(), status_code=error.code,
                        media_type=error.headers.get_content_type())
    except (urllib.error.URLError, TimeoutError, OSError):
        detail = (
            "桌面托盘代理未运行，无法显示扫码或后台窗口。"
            "请先在安装 CreatorHub 的电脑上启动托盘程序。"
        )
        if requested_from_remote:
            detail += (
                "当前请求来自局域网其他电脑；浏览器窗口只会在安装主机显示，"
                "不会在当前访问电脑弹出。"
            )
        return JSONResponse({
            "detail": detail,
        }, status_code=503)


def install_agent_proxy(app, security_path) -> None:
    @app.middleware("http")
    async def visible_browser_proxy(request: Request, call_next):
        if not is_visible_browser_route(request.url.path):
            return await call_next(request)
        token = str(_load(security_path).get("local_token") or "")
        if not token:
            return JSONResponse({"detail": "请先完成管理员初始化"}, 503)
        account_match = re.match(r"^/api/accounts/(\d+)/", request.url.path)
        if account_match:
            try:
                from app import main as core_module
                if core_module.browser is not None:
                    await core_module.browser.close_context(int(account_match.group(1)))
            except Exception:
                pass
        body = await request.body()
        requested_from_remote = not _is_loopback(
            request.client.host if request.client else None)
        return await asyncio.to_thread(
            _forward_sync, request, body, token, requested_from_remote)
