Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

param(
  [string]$Repo = "MarshallEriksen-Neura/AI-Higress-Gateway",
  [string]$Ref = "master",
  [string]$Version = "",
  [string]$InstallDir = ""
)

function Show-Usage {
  @"
Install AI Bridge CLI (bridge) on Windows.

Usage:
  irm https://raw.githubusercontent.com/<owner>/<repo>/<ref>/scripts/install-bridge.ps1 | iex

Options (env vars / params):
  REPO=<owner/repo>          Default: MarshallEriksen-Neura/AI-Higress-Gateway
  REF=<git ref>              Default: master (used for dev artifacts in dist/)
  VERSION=<bridge-vX.Y.Z>    If set, download from GitHub Release assets
  INSTALL_DIR=<dir>          Default: %USERPROFILE%\.local\bin

Notes:
  - Dev artifacts: dist/bridge/bridge_dev_windows_<arch>.zip
  - Release artifacts: bridge_<VERSION>_windows_<arch>.zip
"@ | Write-Output
}

if ($args.Count -gt 0 -and ($args[0] -eq "-h" -or $args[0] -eq "--help")) {
  Show-Usage
  exit 0
}

if ($env:REPO -and $Repo -eq "MarshallEriksen-Neura/AI-Higress-Gateway") { $Repo = $env:REPO }
if ($env:REF -and $Ref -eq "master") { $Ref = $env:REF }
if ($env:VERSION -and [string]::IsNullOrWhiteSpace($Version)) { $Version = $env:VERSION }
if ($env:INSTALL_DIR -and [string]::IsNullOrWhiteSpace($InstallDir)) { $InstallDir = $env:INSTALL_DIR }
if ([string]::IsNullOrWhiteSpace($InstallDir)) { $InstallDir = Join-Path $env:USERPROFILE ".local\\bin" }

$archRaw = ($env:PROCESSOR_ARCHITECTURE ?? "").ToLowerInvariant()
$arch = switch ($archRaw) {
  "amd64" { "amd64" }
  "arm64" { "arm64" }
  default { throw "Unsupported arch: $archRaw (supported: AMD64, ARM64)" }
}

$asset = if (-not [string]::IsNullOrWhiteSpace($Version)) {
  "bridge_${Version}_windows_${arch}.zip"
} else {
  "bridge_dev_windows_${arch}.zip"
}

$url = if (-not [string]::IsNullOrWhiteSpace($Version)) {
  "https://github.com/$Repo/releases/download/$Version/$asset"
} else {
  "https://raw.githubusercontent.com/$Repo/$Ref/dist/bridge/$asset"
}

Write-Output "Installing bridge"
Write-Output "  repo: $Repo"
if (-not [string]::IsNullOrWhiteSpace($Version)) {
  Write-Output "  version: $Version"
} else {
  Write-Output "  ref: $Ref"
}
Write-Output "  asset: $asset"
Write-Output "  url: $url"
Write-Output "  install_dir: $InstallDir"

$tmpRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("bridge-install-" + [guid]::NewGuid().ToString("n"))
$tmp = New-Item -ItemType Directory -Path $tmpRoot -Force
try {
  $archivePath = Join-Path $tmp.FullName $asset
  Invoke-WebRequest -Uri $url -OutFile $archivePath

  $extractDir = Join-Path $tmp.FullName "extract"
  New-Item -ItemType Directory -Path $extractDir -Force | Out-Null
  Expand-Archive -Path $archivePath -DestinationPath $extractDir -Force

  $binSrc = Join-Path $extractDir "bridge.exe"
  if (-not (Test-Path -Path $binSrc)) {
    $found = Get-ChildItem -Path $extractDir -Recurse -Filter "bridge.exe" -File | Select-Object -First 1
    if (-not $found) { throw "bridge.exe not found after extracting archive" }
    $binSrc = $found.FullName
  }

  New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
  $binDst = Join-Path $InstallDir "bridge.exe"
  Copy-Item -Path $binSrc -Destination $binDst -Force

  Write-Output "Installed: $binDst"
  Write-Output "Tip: add to PATH if needed (e.g. setx PATH `"$InstallDir;%PATH%`")"
} finally {
  Remove-Item -Path $tmp.FullName -Recurse -Force -ErrorAction SilentlyContinue
}
