from __future__ import annotations

import json
import os
import ssl
import subprocess
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

import pystray
from PIL import Image, ImageDraw

from . import LAN_PORT, PRODUCT_VERSION
from .agent import start_agent_thread
from .paths import register_operator, runtime_paths


URL = f"https://127.0.0.1:{LAN_PORT}/"


def _icon() -> Image.Image:
    image = Image.new("RGBA", (64, 64), (7, 193, 96, 255))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((5, 5, 59, 59), radius=16, fill=(7, 193, 96, 255))
    draw.ellipse((18, 18, 43, 43), outline="white", width=6)
    draw.line((39, 39, 49, 49), fill="white", width=6)
    return image


def _local_headers() -> dict[str, str]:
    state = runtime_paths().security
    try:
        token = json.loads(state.read_text(encoding="utf-8")).get("local_token", "")
    except (OSError, ValueError):
        token = ""
    return {"X-CreatorHub-Local": token} if token else {}


def _health() -> bool:
    try:
        request = urllib.request.Request(URL + "health", headers=_local_headers())
        context = ssl._create_unverified_context()
        with urllib.request.urlopen(request, context=context, timeout=3) as response:
            return response.status == 200
    except Exception:
        return False


def _open(*_args):
    webbrowser.open(URL)


def _open_data(*_args):
    os.startfile(runtime_paths().program_data)


def _restart_service(*_args):
    subprocess.run(["sc.exe", "stop", "CreatorHubService"], check=False,
                   creationflags=subprocess.CREATE_NO_WINDOW)
    time.sleep(2)
    subprocess.run(["sc.exe", "start", "CreatorHubService"], check=False,
                   creationflags=subprocess.CREATE_NO_WINDOW)


def run_tray() -> int:
    paths = runtime_paths()
    register_operator(paths)
    agent_server, agent_thread = start_agent_thread()
    icon = pystray.Icon(
        "CreatorHub", _icon(), f"CreatorHub {PRODUCT_VERSION}",
        menu=pystray.Menu(
            pystray.MenuItem("打开 CreatorHub", _open, default=True),
            pystray.MenuItem("打开数据目录", _open_data),
            pystray.MenuItem("重启后台服务", _restart_service),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("退出托盘", lambda icon, _item: icon.stop()),
        ),
    )

    def monitor():
        was_healthy = None
        while icon.visible:
            healthy = _health()
            if was_healthy is True and not healthy:
                icon.notify("后台服务已离线，请检查或重启服务。", "CreatorHub")
            was_healthy = healthy
            time.sleep(30)

    threading.Thread(target=monitor, daemon=True).start()
    threading.Timer(1.5, _open).start()
    try:
        icon.run()
    finally:
        agent_server.should_exit = True
        agent_thread.join(timeout=10)
    return 0
