# -*- mode: python ; coding: utf-8 -*-
import os
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

root = Path(SPECPATH).parent
addon_root = Path(os.environ.get(
    "CREATORHUB_WECHAT_OA_PATH", str(root.parent / "CreatorHub-WechatOA")))
addon_data = collect_data_files("creatorhub_wechat_oa")
patchright_data = collect_data_files("patchright", includes=["driver/**"])
datas = [
    (str(root / "config.example.yaml"), "."),
    (str(root / "app" / "web"), "app/web"),
] + addon_data + patchright_data
hidden = (
    collect_submodules("uvicorn")
    + collect_submodules("patchright")
    + collect_submodules("creatorhub_wechat_oa")
    + ["win32timezone", "servicemanager", "pystray._win32"]
)

common = dict(
    pathex=[str(root), str(addon_root)], datas=datas,
    hiddenimports=hidden, hookspath=[], hooksconfig={},
    runtime_hooks=[], excludes=["pytest"], noarchive=False,
)

service_a = Analysis([str(root / "windows_entries" / "service_entry.py")], **common)
service_pyz = PYZ(service_a.pure)
service_exe = EXE(service_pyz, service_a.scripts, [], exclude_binaries=True,
                  name="CreatorHubService", console=False,
                  disable_windowed_traceback=False, uac_admin=True)

tray_a = Analysis([str(root / "windows_entries" / "tray_entry.py")], **common)
tray_pyz = PYZ(tray_a.pure)
tray_exe = EXE(tray_pyz, tray_a.scripts, [], exclude_binaries=True,
               name="CreatorHubTray", console=False,
               disable_windowed_traceback=False)

tools_a = Analysis([str(root / "windows_entries" / "tools_entry.py")], **common)
tools_pyz = PYZ(tools_a.pure)
tools_exe = EXE(tools_pyz, tools_a.scripts, [], exclude_binaries=True,
                name="CreatorHubTools", console=True,
                disable_windowed_traceback=False)

coll = COLLECT(
    service_exe, tray_exe, tools_exe,
    service_a.binaries, service_a.datas,
    tray_a.binaries, tray_a.datas,
    tools_a.binaries, tools_a.datas,
    name="CreatorHub",
)
