"""CreatorHub + 独立微信公众号扩展的最小组合入口。"""
from __future__ import annotations

import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
ADDON_ROOT = Path(os.getenv(
    "CREATORHUB_WECHAT_OA_PATH",
    str(ROOT.parent / "CreatorHub-WechatOA"),
)).resolve()

if not (ADDON_ROOT / "creatorhub_wechat_oa" / "__init__.py").is_file():
    raise RuntimeError(
        f"找不到微信公众号独立仓库：{ADDON_ROOT}。"
        "请设置 CREATORHUB_WECHAT_OA_PATH，或把仓库放在 CreatorHub 同级目录。"
    )

sys.path.insert(0, str(ADDON_ROOT))

import app.main as core  # noqa: E402
from creatorhub_wechat_oa import install  # noqa: E402


install(core.app, core)
app = core.app
