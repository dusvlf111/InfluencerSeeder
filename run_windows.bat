@echo off
setlocal enabledelayedexpansion
chcp 65001 > nul 2>&1
:: InfluencerSeeder - Run script (Windows)
:: Double-click this file to run the app directly from source.
:: (For installation/packaging, use build_windows.bat)

:: This script sits next to src\; the app sources live inside src\.
cd /d "%~dp0src"

:: All command output/errors are captured here so the window can show them.
set "LOGFILE=%~dp0run_error.log"
if exist "%LOGFILE%" del "%LOGFILE%" > nul 2>&1

echo.
echo ============================================================
echo   InfluencerSeeder - Run (Windows)
echo ============================================================
echo.

:: ----- Step 1: Check Python -----
set PYTHON_CMD=
python --version > nul 2>&1
if not errorlevel 1 (
    set PYTHON_CMD=python
    goto :PYTHON_OK
)
py -3 --version > nul 2>&1
if not errorlevel 1 (
    set PYTHON_CMD=py -3
    goto :PYTHON_OK
)
echo [ERROR] Python is not installed.
echo         Install Python from https://www.python.org and run again.
echo         (Recommended: check "Add Python to PATH" during install)
goto :fail

:PYTHON_OK
for /f "tokens=*" %%v in ('!PYTHON_CMD! --version 2^>^&1') do set PYTHON_VERSION=%%v
echo [1/3] Python: !PYTHON_VERSION!

:: 수집은 임베디드 QtWebEngine(Chromium 내장)에서 진행 — 시스템 Chrome 불필요.

:: ----- Step 2: Virtual environment + dependencies -----
:: Reuse the same venv as build_windows.bat (skips fast if it already exists).
set VENV_PY=.venv_win\Scripts\python.exe
set VENV_PYW=.venv_win\Scripts\pythonw.exe

if not exist "%VENV_PY%" (
    echo [2/3] First run: creating venv and installing dependencies (2-5 min)...
    !PYTHON_CMD! -m venv .venv_win > "%LOGFILE%" 2>&1
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment.
        goto :fail
    )
    "%VENV_PY%" -m pip install --upgrade pip --no-warn-script-location >> "%LOGFILE%" 2>&1
    "%VENV_PY%" -m pip install -r requirements.txt --no-warn-script-location >> "%LOGFILE%" 2>&1
    if errorlevel 1 (
        echo [ERROR] Failed to install dependencies.
        goto :fail
    )
) else (
    :: Check that the Qt + WebEngine runtime is actually loadable
    "%VENV_PY%" -c "from PyQt6.QtWidgets import QApplication; from PyQt6.QtWebEngineWidgets import QWebEngineView" > nul 2>&1
    if errorlevel 1 (
        echo [2/3] Installing missing dependencies...
        "%VENV_PY%" -m pip install -r requirements.txt --no-warn-script-location >> "%LOGFILE%" 2>&1
        if errorlevel 1 (
            echo [ERROR] Failed to install dependencies.
            goto :fail
        )
    ) else (
        echo [2/3] Virtual environment OK.
    )
)

:: ----- Step 3: Launch app -----
:: Use pythonw.exe (no console window) so the CMD launcher can close cleanly.
:: Errors are captured in run_error.log; if the app crashes within 3 seconds
:: this window re-opens to show the log.
echo [3/3] Starting app...
echo.

if not exist "%VENV_PYW%" set VENV_PYW=%VENV_PY%

:: Write PID sentinel so we can detect an immediate crash
if exist "%~dp0run_pid.tmp" del "%~dp0run_pid.tmp" > nul 2>&1

start "" "%VENV_PYW%" main.py 2>"%LOGFILE%"

:: Wait 3 seconds — if the log file is non-empty the app crashed immediately
timeout /t 3 /nobreak > nul 2>&1

if exist "%LOGFILE%" (
    for %%A in ("%LOGFILE%") do if %%~zA gtr 0 goto :fail_log
)

:: Clean exit — remove empty log and close this window
if exist "%LOGFILE%" del "%LOGFILE%" > nul 2>&1
exit /b 0

:fail_log
echo.
echo ============================================================
echo [ERROR] App crashed at startup. Details:
echo ------------------------------------------------------------
type "%LOGFILE%"
echo ------------------------------------------------------------
echo Full log saved to: %LOGFILE%
echo ============================================================
echo.
echo This window stays open so you can read the error.
pause
exit /b 1

:fail
echo.
echo ============================================================
echo [ERROR] A problem occurred. Details:
echo ------------------------------------------------------------
if exist "%LOGFILE%" (
    type "%LOGFILE%"
    echo ------------------------------------------------------------
    echo Full log saved to: %LOGFILE%
) else (
    echo ^(see the messages above^)
)
echo ============================================================
echo.
echo This window stays open so you can read the error.
pause
exit /b 1
