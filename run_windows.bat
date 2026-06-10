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

:: ----- Ensure Google Chrome (Selenium launches it; NSS DLLs ship inside Chrome) -----
set "CHROME_FOUND="
if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" set "CHROME_FOUND=1"
if exist "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" set "CHROME_FOUND=1"
if exist "%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe" set "CHROME_FOUND=1"
if defined CHROME_FOUND goto :CHROME_OK
echo       Chrome not found. Installing via winget...
winget --version > nul 2>&1
if errorlevel 1 (
    echo [WARN] winget unavailable. Install Chrome from https://www.google.com/chrome/
    goto :CHROME_OK
)
winget install Google.Chrome --silent --accept-package-agreements --accept-source-agreements > nul 2>&1
:CHROME_OK

:: ----- Step 2: Virtual environment + dependencies -----
:: Reuse the same venv as build_windows.bat (skips fast if it already exists).
set VENV_PY=.venv_win\Scripts\python.exe

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
    "%VENV_PY%" -c "import PyQt6, selenium, webdriver_manager" > nul 2>&1
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

:: ----- Step 3: Launch app (capture stderr so a crash leaves a readable log) -----
echo [3/3] Starting app...
echo.
"%VENV_PY%" main.py 2> "%LOGFILE%"
if errorlevel 1 goto :fail

:: Normal exit — clean up the (empty) log.
if exist "%LOGFILE%" del "%LOGFILE%" > nul 2>&1
exit /b 0

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
