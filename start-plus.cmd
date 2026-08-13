@echo off
setlocal
cd /d "%~dp0"

set "CREATORHUB_PY=%~dp0.venv\Scripts\python.exe"
if not exist "%CREATORHUB_PY%" (
  echo [CreatorHub] 尚未安装，请先运行 python creatorhub.py install
  exit /b 1
)

if not defined CREATORHUB_WECHAT_OA_PATH set "CREATORHUB_WECHAT_OA_PATH=%~dp0..\CreatorHub-WechatOA"

echo [CreatorHub] 正在启动核心与独立微信公众号扩展...
"%CREATORHUB_PY%" -m uvicorn creatorhub_plus:app --host 127.0.0.1 --port 8000
