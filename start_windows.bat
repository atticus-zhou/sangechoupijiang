@echo off
setlocal

cd /d "%~dp0"

set "CHECK_ONLY=0"
if /I "%~1"=="--check" (
  set "CHECK_ONLY=1"
  set "PORT=%~2"
) else (
  set "PORT=%~1"
)

if "%PORT%"=="" set "PORT=8080"

echo.
echo Three Cobblers local starter
echo Repository: %CD%
echo Port: %PORT%
echo.

where python >nul 2>nul
if errorlevel 1 (
  echo Python was not found on PATH.
  echo Install Python 3.11 or newer, then run this file again.
  exit /b 1
)

if not exist "requirements.txt" (
  echo requirements.txt was not found. Please run this from the repository root.
  exit /b 1
)

python -c "import fastapi, uvicorn, yaml, docx, PIL, requests" >nul 2>nul
if errorlevel 1 (
  echo Missing Python dependencies. Installing requirements.txt...
  python -m pip install -r requirements.txt
  if errorlevel 1 (
    echo Dependency installation failed. Fix the pip error above and run again.
    exit /b 1
  )
)

if not exist "config.yaml" (
  if exist "config.example.yaml" (
    echo config.yaml not found. Creating it from config.example.yaml.
    copy "config.example.yaml" "config.yaml" >nul
  )
)

echo.
echo Running local doctor before startup...
python scripts\doctor.py --format markdown
if errorlevel 1 (
  echo.
  echo Doctor found a startup blocker. Fix the item above, then run this file again.
  exit /b 1
)

if "%CHECK_ONLY%"=="1" (
  echo.
  echo Check-only mode passed. The server was not started.
  exit /b 0
)

echo.
echo Starting local app. Open http://127.0.0.1:%PORT%/
echo Press Ctrl+C in this window to stop the server.
python run.py --port %PORT%
