# CreatorHub Windows 一体化版

## 运行结构

- `CreatorHubService`：后台监控、公众号官方 API、HTTPS、备份和更新检查。
- `CreatorHubTray`：随当前用户登录启动，负责所有扫码、重新登录、打开平台后台和公众号真实健康检测。
- 系统 Google Chrome Stable：不内置另一份浏览器；各账号继续使用独立画像。
- CreatorHub 核心与 `CreatorHub-WechatOA` 仍是两个独立源码仓库，安装包只在构建时组合二者。

服务监听 `https://0.0.0.0:8443`。首次打开必须在安装电脑上设置至少 10 位管理员密码，完成后才能从局域网访问。

## 数据位置

- 数据库、配置、密钥、日志、备份：`%PROGRAMDATA%\CreatorHub`
- 核心浏览器画像：`%LOCALAPPDATA%\CreatorHub\profiles`
- 公众号浏览器画像：`%LOCALAPPDATA%\CreatorHub\wechat_oa\profiles`
- 每日 03:10 创建加密备份，保留 14 天；备份不包含体积较大的浏览器画像。

卸载默认保留上述数据。只有在卸载最后一步明确确认时，才会删除 ProgramData 和当前用户的 LocalAppData 数据。

## 构建

要求 Windows 10/11 x64、Python 虚拟环境、Inno Setup 6，以及与核心仓库同级的 `CreatorHub-WechatOA` 仓库：

```powershell
powershell -ExecutionPolicy Bypass -File packaging\build-windows.ps1
```

脚本使用 PyInstaller `onedir` 构建三个程序，下载官方便携 Node 运行时，然后由 Inno Setup 生成：

`release\CreatorHub-Setup-1.0.1-x64.exe`

若公众号仓库不在默认同级路径，可预先设置 `CREATORHUB_WECHAT_OA_PATH`。

## 安装与更新

安装程序要求管理员权限并检查系统 Chrome。它会复制但不删除旧版 `D:\recod\CreatorHub` 数据，安装后台服务、添加私有网络 8443 防火墙规则并启动托盘。

“内部版本更新”页面可保存私有 GitHub Release 的只读 Token。Token 进入 Windows 凭据管理器，不写入配置文件；更新安装包经大小和 GitHub SHA-256 摘要校验后，由桌面托盘显示安装确认窗口。

当前 1.0.1 为内部测试包，尚未购买代码签名证书，因此 Windows 会显示“未知发布者”。正式分发前应加入 Authenticode 签名。
