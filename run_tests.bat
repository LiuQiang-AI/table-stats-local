@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo [test] Create venv...
  python -m venv .venv
  if errorlevel 1 exit /b 1
)

echo [test] Install requirements (use official PyPI)...
".venv\Scripts\python.exe" -m pip install -i https://pypi.org/simple -r requirements.txt
if errorlevel 1 exit /b 1

echo [test] Run smoke tests...
".venv\Scripts\python.exe" -m unittest discover -s tests -p "test_*.py" -v

