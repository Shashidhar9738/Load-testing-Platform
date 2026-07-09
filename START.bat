@echo off
setlocal EnableExtensions

cd /d "%~dp0" || (
    echo.
    echo ERROR: Failed to switch to project directory.
    pause
    exit /b 1
)

title Load Testing Platform - Setup and Start
set "LT_WEBHOOK_SKIP_TLS=1"
color 0A
cls

echo.
echo  ============================================================
echo   Load Testing Platform ^| BTC
echo  ============================================================
echo.

set "PYTHON_CMD="
where python >nul 2>&1
if not errorlevel 1 set "PYTHON_CMD=python"

if not defined PYTHON_CMD (
    where py >nul 2>&1
    if not errorlevel 1 set "PYTHON_CMD=py -3"
)

echo  [1/4] Checking Python...
if not defined PYTHON_CMD (
    color 0C
    echo.
    echo ERROR: Python not found.
    echo Install Python 3 and re-run START.bat
    echo.
    pause
    exit /b 1
)

for /f "delims=" %%v in ('%PYTHON_CMD% --version 2^>^&1') do set "PYVER=%%v"
echo         Found: %PYVER%
echo.

echo  [2/4] Upgrading pip...
%PYTHON_CMD% -m pip install --upgrade pip --quiet
if errorlevel 1 (
    color 0E
    echo.
    echo WARNING: pip upgrade failed, continuing...
    echo.
)
echo.

echo  [3/4] Installing dependencies from requirements.txt...
if not exist requirements.txt (
    color 0C
    echo.
    echo ERROR: requirements.txt not found in:
    echo        %cd%
    echo.
    pause
    exit /b 1
)

%PYTHON_CMD% -m pip install -r requirements.txt --quiet
if errorlevel 1 (
    color 0C
    echo.
    echo ERROR: Failed to install one or more packages.
    echo Check your internet connection and try again.
    echo.
    pause
    exit /b 1
)
echo         All packages installed.
echo.

echo  [4/4] Starting server...
echo.
echo  ============================================================
echo   Open in browser: http://localhost:5000
echo.
echo   Default credentials are in README.md (change after first login).
echo.
echo   Press Ctrl+C to stop the server.
echo  ============================================================
echo.

if not exist app.py (
    color 0C
    echo.
    echo ERROR: app.py not found in:
    echo        %cd%
    echo.
    pause
    exit /b 1
)

%PYTHON_CMD% app.py
set "RC=%errorlevel%"

echo.
echo Server process exited with code %RC%.
echo Working directory: %cd%
pause
exit /b %RC%
