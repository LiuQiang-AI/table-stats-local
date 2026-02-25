@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo [run] Create venv...
  python -m venv .venv
  if errorlevel 1 exit /b 1
)

echo [run] Install requirements (use official PyPI)...
".venv\Scripts\python.exe" -m pip install -i https://pypi.org/simple -r requirements.txt
if errorlevel 1 exit /b 1

echo [run] Launch app...
".venv\Scripts\python.exe" main.py

@echo off
setlocal

cd /d "%~dp0"

set "MODE=%~1"
set "PORT=%~2"
if "%MODE%"=="" set "MODE=v6"
if "%PORT%"=="" set "PORT=8787"

if /I "%MODE%"=="v4" (
  set "HOST=0.0.0.0"
  set "OPEN_URL=http://127.0.0.1:%PORT%"
) else (
  rem v6 (default): listen on all IPv6 interfaces (and usually IPv4 too).
  set "HOST=::"
  set "OPEN_URL=http://[::1]:%PORT%"
)

start "" "%OPEN_URL%"
python server.py --host %HOST% --port %PORT%

endlocal

