#define MyAppName "CreatorHub"
#define MyAppVersion "1.0.1"
#define MyAppPublisher "gmlgaobo"
#define MyAppExeName "CreatorHubTray.exe"

[Setup]
AppId={{B31CC8B5-A228-43B6-9303-E6105BA0B776}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\CreatorHub
DefaultGroupName=CreatorHub
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
OutputDir=..\release
OutputBaseFilename=CreatorHub-Setup-{#MyAppVersion}-x64
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#MyAppExeName}
ChangesAssociations=no
CloseApplications=yes
RestartApplications=no

[Files]
Source: "..\dist\CreatorHub\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\config.example.yaml"; DestDir: "{app}\_internal"; Flags: ignoreversion
Source: "..\packaging\vendor\node\*"; DestDir: "{app}\vendor\node"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\node_modules\crypto-js\*"; DestDir: "{app}\node_modules\crypto-js"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\CreatorHub"; Filename: "{app}\CreatorHubTray.exe"
Name: "{autodesktop}\CreatorHub"; Filename: "{app}\CreatorHubTray.exe"

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "CreatorHubTray"; ValueData: """{app}\CreatorHubTray.exe"""; Flags: uninsdeletevalue

[Run]
Filename: "{app}\CreatorHubTools.exe"; Parameters: "migrate-auto"; StatusMsg: "正在检查旧版 CreatorHub 数据..."; Flags: waituntilterminated
Filename: "{app}\CreatorHubTools.exe"; Parameters: "prepare"; StatusMsg: "正在初始化数据目录和 HTTPS 证书..."; Flags: runhidden waituntilterminated
Filename: "icacls.exe"; Parameters: """{commonappdata}\CreatorHub"" /inheritance:r /grant:r ""SYSTEM:(OI)(CI)F"" ""Administrators:(OI)(CI)F"" ""{username}:(OI)(CI)M"""; StatusMsg: "正在保护数据库和密钥..."; Flags: runhidden waituntilterminated
Filename: "certutil.exe"; Parameters: "-addstore -user Root ""{commonappdata}\CreatorHub\certificates\creatorhub.crt"""; StatusMsg: "正在信任本机 HTTPS 证书..."; Flags: runhidden waituntilterminated
Filename: "{app}\CreatorHubService.exe"; Parameters: "--startup auto install"; StatusMsg: "正在安装后台服务..."; Flags: runhidden waituntilterminated
Filename: "sc.exe"; Parameters: "failure CreatorHubService reset= 86400 actions= restart/5000/restart/15000/none/0"; Flags: runhidden waituntilterminated
Filename: "netsh.exe"; Parameters: "advfirewall firewall add rule name=""CreatorHub HTTPS"" dir=in action=allow protocol=TCP localport=8443 profile=private"; Flags: runhidden waituntilterminated
Filename: "{app}\CreatorHubService.exe"; Parameters: "start"; StatusMsg: "正在启动后台服务..."; Flags: runhidden waituntilterminated
Filename: "{app}\CreatorHubTray.exe"; Description: "启动 CreatorHub"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{app}\CreatorHubService.exe"; Parameters: "stop"; Flags: runhidden waituntilterminated; RunOnceId: "StopService"
Filename: "{app}\CreatorHubService.exe"; Parameters: "remove"; Flags: runhidden waituntilterminated; RunOnceId: "RemoveService"
Filename: "netsh.exe"; Parameters: "advfirewall firewall delete rule name=""CreatorHub HTTPS"""; Flags: runhidden waituntilterminated; RunOnceId: "RemoveFirewall"

[Code]
function ChromeInstalled(): Boolean;
var
  Value: String;
begin
  Result := RegQueryStringValue(HKLM64, 'Software\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe', '', Value)
    or RegQueryStringValue(HKCU, 'Software\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe', '', Value);
end;

function InitializeSetup(): Boolean;
begin
  Result := ChromeInstalled();
  if not Result then
    MsgBox('CreatorHub 需要 Google Chrome Stable。请先安装官方 Chrome 后重新运行安装程序。', mbCriticalError, MB_OK);
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
  begin
    if MsgBox('默认已保留账号、数据库、密钥和浏览器画像。是否彻底删除本机 CreatorHub 的全部运行数据？', mbConfirmation, MB_YESNO) = IDYES then
    begin
      DelTree(ExpandConstant('{commonappdata}\CreatorHub'), True, True, True);
      DelTree(ExpandConstant('{localappdata}\CreatorHub'), True, True, True);
    end;
  end;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  ResultCode: Integer;
begin
  Result := '';
  if FileExists(ExpandConstant('{app}\CreatorHubService.exe')) then
    Exec(ExpandConstant('{app}\CreatorHubService.exe'), 'stop', '', SW_HIDE,
      ewWaitUntilTerminated, ResultCode);
end;
