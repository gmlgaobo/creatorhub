"""CreatorHub + 独立微信公众号扩展的最小组合入口。"""
from __future__ import annotations

import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
try:
    import creatorhub_wechat_oa as _installed_addon  # noqa: F401
except ImportError:
    ADDON_ROOT = Path(os.getenv(
        "CREATORHUB_WECHAT_OA_PATH",
        str(ROOT.parent / "CreatorHub-WechatOA"),
    )).resolve()
    if not (ADDON_ROOT / "creatorhub_wechat_oa" / "__init__.py").is_file():
        raise RuntimeError(
            f"找不到微信公众号独立仓库：{ADDON_ROOT}。"
            "请设置 CREATORHUB_WECHAT_OA_PATH，或安装 creatorhub-wechat-oa。"
        )
    sys.path.insert(0, str(ADDON_ROOT))

import app.main as core  # noqa: E402
from creatorhub_wechat_oa import install  # noqa: E402


install(core.app, core)
app = core.app
