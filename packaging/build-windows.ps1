param(
  [switch]$SkipNode,
  [switch]$SkipInstaller
)

$ErrorActionPreference = 'Stop'
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Python = Join-Path $RepoRoot '.venv\Scripts\python.exe'
$AddonRoot = if ($env:CREATORHUB_WECHAT_OA_PATH) {
  $env:CREATORHUB_WECHAT_OA_PATH
} else {
  Join-Path (Split-Path $RepoRoot -Parent) 'CreatorHub-WechatOA'
}
$NodeVersion = '24.18.1'
$VendorRoot = Join-Path $RepoRoot 'packaging\vendor'
$NodeRoot = Join-Path $VendorRoot 'node'

if (-not (Test-Path -LiteralPath $Python)) { throw 'Missing .venv. Install CreatorHub dependencies first.' }
if (-not (Test-Path -LiteralPath (Join-Path $AddonRoot 'pyproject.toml'))) {
  throw 'Missing CreatorHub-WechatOA sibling repository.'
}

& $Python -m pip install --upgrade pyinstaller pywin32 pystray pillow
& $Python -m pip install -e $AddonRoot

if (-not $SkipNode -and -not (Test-Path (Join-Path $NodeRoot 'node.exe'))) {
  New-Item -ItemType Directory -Force -Path $VendorRoot | Out-Null
  $Archive = Join-Path $VendorRoot "node-v$NodeVersion-win-x64.zip"
  Invoke-WebRequest "https://nodejs.org/dist/v$NodeVersion/node-v$NodeVersion-win-x64.zip" -OutFile $Archive
  $Extract = Join-Path $VendorRoot "node-v$NodeVersion-win-x64"
  Expand-Archive -LiteralPath $Archive -DestinationPath $VendorRoot -Force
  if (Test-Path -LiteralPath $NodeRoot) {
    $vendorPath = [IO.Path]::GetFullPath($VendorRoot).TrimEnd('\') + '\'
    $nodePath = [IO.Path]::GetFullPath($NodeRoot)
    if (-not $nodePath.StartsWith($vendorPath, [StringComparison]::OrdinalIgnoreCase) -or
        [IO.Path]::GetFileName($nodePath) -ne 'node') {
      throw "Refusing to replace unexpected Node directory: $nodePath"
    }
    Remove-Item -LiteralPath $nodePath -Recurse -Force
  }
  Move-Item -LiteralPath $Extract -Destination $NodeRoot
}

Push-Location $RepoRoot
try {
  & $Python -m PyInstaller --noconfirm --clean 'packaging\CreatorHub.spec'
  if (-not $SkipInstaller) {
    $Iscc = @(
      'C:\Program Files (x86)\Inno Setup 6\ISCC.exe',
      'C:\Program Files\Inno Setup 6\ISCC.exe',
      (Join-Path $env:LOCALAPPDATA 'Programs\Inno Setup 6\ISCC.exe')
    ) | Where-Object { Test-Path $_ } | Select-Object -First 1
    if (-not $Iscc) { throw 'Inno Setup 6 is required to build the installer.' }
    & $Iscc 'installer\CreatorHub.iss'
  }
} finally {
  Pop-Location
}
