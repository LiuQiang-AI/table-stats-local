param(
  [string]$Distro = "",
  [string]$BuildType = "debug"
)

$ErrorActionPreference = "Stop"

function AssertWSLInstalled() {
  $wsl = (Get-Command wsl.exe -ErrorAction SilentlyContinue)
  if (-not $wsl) {
    throw "wsl.exe not found. Install WSL first (Admin PowerShell): wsl.exe --install"
  }

  # Avoid triggering the interactive WSL installer prompt when WSL is not installed.
  $lxssHKCU = Test-Path 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Lxss'
  $lxssHKLM = Test-Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Lxss'
  if (-not $lxssHKCU -and -not $lxssHKLM) {
    Write-Host '[build] WSL is not installed (Lxss registry key not found).'
    Write-Host '[build] Run (Admin PowerShell): wsl.exe --install'
    Write-Host '[build] Reboot Windows, then open Ubuntu once to finish initialization.'
    throw 'WSL not installed. Stop.'
  }

  # Check that at least one distro exists. If none, ask user to install Ubuntu once.
  $distros = & wsl.exe -l -q
  if ($LASTEXITCODE -ne 0) {
    Write-Host '[build] wsl.exe returned error when listing distributions.'
    Write-Host '[build] Try (Admin PowerShell): wsl.exe --install -d Ubuntu'
    throw 'WSL not ready. Stop.'
  }
  if (-not $distros -or ($distros | Measure-Object).Count -eq 0) {
    Write-Host '[build] No WSL distro installed.'
    Write-Host '[build] Install one (Admin PowerShell): wsl.exe --install -d Ubuntu'
    throw 'No WSL distro installed. Stop.'
  }
}

function RunWSL([string]$Cmd) {
  if ($Distro -and $Distro.Trim().Length -gt 0) {
    wsl.exe -d $Distro -- bash -lc $Cmd
  } else {
    wsl.exe -- bash -lc $Cmd
  }
}

Set-Location -Path $PSScriptRoot

Write-Host '[build] Using WSL to build Android APK (Buildozer)'

AssertWSLInstalled

# WSL path, e.g. /mnt/e/table-stats-local
$drive = (Get-Item $PSScriptRoot).PSDrive.Name.ToLower()
$pathPart = ($PSScriptRoot.Substring(2) -replace "\\","/")
$wslPath = "/mnt/$drive$pathPart"

Write-Host "[build] Project path in WSL: $wslPath"

# Prepare buildozer.spec if missing
if (-not (Test-Path -Path (Join-Path $PSScriptRoot "buildozer.spec"))) {
  if (Test-Path -Path (Join-Path $PSScriptRoot "buildozer.spec.example")) {
    Copy-Item -Force (Join-Path $PSScriptRoot "buildozer.spec.example") (Join-Path $PSScriptRoot "buildozer.spec")
    Write-Host '[build] Copied buildozer.spec.example -> buildozer.spec'
  } else {
    throw "Missing buildozer.spec.example"
  }
}

# Minimal dependencies (may take time on first run)
RunWSL "set -e; cd '$wslPath'; sudo apt-get update -y; sudo apt-get install -y python3 python3-pip python3-venv git zip unzip openjdk-17-jdk libffi-dev libssl-dev build-essential"

# Buildozer
RunWSL "set -e; cd '$wslPath'; python3 -m pip install --upgrade pip setuptools wheel; python3 -m pip install buildozer==1.5.0"

# Build
if ($BuildType -ne "debug" -and $BuildType -ne "release") {
  throw "BuildType must be debug or release"
}

RunWSL "set -e; cd '$wslPath'; buildozer -v android $BuildType"

Write-Host '[build] Done. Check ./bin/ for APK.'

