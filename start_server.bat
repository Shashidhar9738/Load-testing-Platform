@echo off
setlocal EnableExtensions
cd /d "%~dp0" || (
	echo Failed to switch to project folder.
	pause
	exit /b 1
)

set "PYTHON_CMD=python"
set "PYTHON_TEST=python --version"
where python >nul 2>&1
if errorlevel 1 (
	where py >nul 2>&1
	if not errorlevel 1 (
		set "PYTHON_CMD=py -3"
		set "PYTHON_TEST=py -3 --version"
	)
)

%PYTHON_TEST% >nul 2>&1
if errorlevel 1 (
	echo Python was not found. Install Python 3 and try again.
	pause
	exit /b 1
)

title Load Testing Platform
set "LT_WEBHOOK_SKIP_TLS=1"
echo ===================================================
echo   Load Testing Platform  v4.0
echo   Centralized Performance Testing Repository
echo ===================================================
echo   Starting server at http://localhost:5000
echo.
echo   Default credentials are in README.md (change after first login).
echo.
echo   Press Ctrl+C to stop the server.
echo ===================================================

if not exist app.py (
	echo ERROR: app.py not found in %cd%
	pause
	exit /b 1
)

%PYTHON_CMD% app.py
echo.
echo Server process exited with code %errorlevel%.
pause
