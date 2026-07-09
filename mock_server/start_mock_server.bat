@echo off
echo ============================================================
echo  Mock Upload Server — Load Testing Platform
echo  Listens on http://localhost:5001
echo  Endpoints:
echo    GET  /health
echo    POST /api/upload/jmx        (.jmx files)
echo    POST /api/upload/testdata   (.csv files)
echo    POST /api/upload/report     (.jtl/.html files)
echo ============================================================
echo.

cd /d "%~dp0"

where python >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found in PATH. Please install Python 3.9+.
    pause
    exit /b 1
)

python -c "import flask" >nul 2>&1
if errorlevel 1 (
    echo Installing flask...
    pip install flask
)

echo Starting mock server...
python mock_upload_server.py
pause
