@echo off
setlocal enabledelayedexpansion
chcp 65001 > nul 2>&1

:: This script sits next to src\; the app sources live inside src\.
cd /d "%~dp0src"

:: pip / PyInstaller output is captured here so errors stay readable.
set "LOGFILE=%~dp0build_error.log"
if exist "%LOGFILE%" del "%LOGFILE%" > nul 2>&1

echo.
echo ============================================================
echo   InfluencerSeeder - Windows Build Script
echo ============================================================
echo.

:: -------------------------------------------------------
:: Step 1: Find Python
:: -------------------------------------------------------
echo [1/5] Checking Python...

set PYTHON_CMD=
set PYTHON_VERSION=

python --version > nul 2>&1
if not errorlevel 1 (
    set PYTHON_CMD=python
    for /f "tokens=*" %%v in ('python --version 2^>^&1') do set PYTHON_VERSION=%%v
    echo       Found: !PYTHON_VERSION!
    goto :PYTHON_OK
)

py -3 --version > nul 2>&1
if not errorlevel 1 (
    set PYTHON_CMD=py -3
    for /f "tokens=*" %%v in ('py -3 --version 2^>^&1') do set PYTHON_VERSION=%%v
    echo       Found: !PYTHON_VERSION!
    goto :PYTHON_OK
)

echo       Python not found. Installing Python 3.12 via winget...
echo.
winget --version > nul 2>&1
if errorlevel 1 (
    echo [ERROR] winget is not available.
    echo         Install Python manually from https://www.python.org then re-run.
    goto :fail
)
echo       Downloading Python 3.12 (this may take a few minutes)...
winget install Python.Python.3.12 --silent --accept-package-agreements --accept-source-agreements
if errorlevel 1 (
    echo [ERROR] Python installation failed. Install manually from https://www.python.org
    goto :fail
)
set "PATH=%LOCALAPPDATA%\Programs\Python\Python312;%LOCALAPPDATA%\Programs\Python\Python312\Scripts;%PATH%"
python --version > nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python installed but not on PATH. Close this window, reopen, and re-run.
    goto :fail
)
set PYTHON_CMD=python
for /f "tokens=*" %%v in ('python --version 2^>^&1') do set PYTHON_VERSION=%%v
echo       Installed: !PYTHON_VERSION!

:PYTHON_OK

rem --- Require Python 3.10+ (PEP 604 union syntax is evaluated at runtime) ---
rem  Parse the version string in batch (no inline python with parens, which
rem  would break cmd's block-paren counting and corrupt later lines).
call :PYVER_OK "!PYTHON_VERSION!"
if not errorlevel 1 goto :PYVER_DONE
echo       Python is older than 3.10 - trying py launcher 3.12/3.11/3.10...
set "PYTHON_CMD="
for %%V in (3.12 3.11 3.10) do (
    if not defined PYTHON_CMD (
        py -%%V --version >nul 2>&1
        if not errorlevel 1 set "PYTHON_CMD=py -%%V"
    )
)
if not defined PYTHON_CMD (
    echo [ERROR] Python 3.10+ is required. Get it from https://www.python.org/downloads/
    goto :fail
)
for /f "tokens=*" %%v in ('!PYTHON_CMD! --version 2^>^&1') do set "PYTHON_VERSION=%%v"
echo       Using: !PYTHON_VERSION!
:PYVER_DONE

:: 수집은 임베디드 QtWebEngine(Chromium 내장) 브라우저에서 진행 — 시스템 Chrome 불필요.

:: -------------------------------------------------------
:: Step 2: Create virtual environment
:: -------------------------------------------------------
echo.
echo [2/5] Setting up virtual environment...
rem --- recreate venv if it was built with Python older than 3.10 ---
if exist ".venv_win\Scripts\python.exe" (
    for /f "tokens=*" %%v in ('.venv_win\Scripts\python.exe --version 2^>^&1') do set "_VENVVER=%%v"
    call :PYVER_OK "!_VENVVER!"
    if errorlevel 1 (
        echo       Existing .venv_win is older than 3.10 - recreating.
        rmdir /s /q .venv_win
    )
)
if exist ".venv_win\Scripts\python.exe" (
    echo       .venv_win already exists, skipping.
) else (
    !PYTHON_CMD! -m venv .venv_win > "%LOGFILE%" 2>&1
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment.
        goto :fail
    )
    echo       Created .venv_win
)

set VENV_PY=.venv_win\Scripts\python.exe

:: -------------------------------------------------------
:: Step 3: Install packages (from requirements.txt + pyinstaller)
::   requirements.txt includes PyQt6-WebEngine — required for the embedded
::   Instagram browser. Installing from the file keeps deps in one place.
:: -------------------------------------------------------
echo.
echo [3/5] Installing packages (first run takes 2-5 minutes)...
echo.

%VENV_PY% -m pip install --upgrade pip --no-warn-script-location >> "%LOGFILE%" 2>&1

echo       Installing from requirements.txt (PyQt6, PyQt6-WebEngine)...
%VENV_PY% -m pip install -r requirements.txt --no-warn-script-location >> "%LOGFILE%" 2>&1
if errorlevel 1 (
    echo [ERROR] Failed to install requirements.txt
    goto :fail
)

echo       Installing pyinstaller...
%VENV_PY% -m pip install pyinstaller --no-warn-script-location >> "%LOGFILE%" 2>&1
if errorlevel 1 (
    echo [ERROR] Failed to install pyinstaller
    goto :fail
)
echo       All packages installed.

:: -------------------------------------------------------
:: Step 4: Build (onedir — required for the embedded QtWebEngine browser)
:: -------------------------------------------------------
echo.
echo [4/5] Building app with PyInstaller (onedir, 2-5 minutes, please wait)...
echo.

if exist "build_tmp" rmdir /s /q build_tmp

:: Output the app folder next to src\ (project root = this script's folder).
pushd "%~dp0"
set "OUT_DIR=%CD%"
popd

%VENV_PY% -m PyInstaller build.spec --distpath "%OUT_DIR%" --workpath build_tmp --noconfirm >> "%LOGFILE%" 2>&1
if errorlevel 1 (
    echo [ERROR] Build failed.
    goto :fail
)

:: -------------------------------------------------------
:: Step 5: Done
:: -------------------------------------------------------
echo.
echo [5/5] Build complete!
echo.
echo ============================================================
echo.

:: onedir output is a folder under OUT_DIR; find the launcher .exe inside it.
set "EXE_FILE="
set "APP_DIR="
for /d %%d in ("%OUT_DIR%\*") do (
    for %%f in ("%%d\*.exe") do (
        set "EXE_FILE=%%~ff"
        set "APP_DIR=%%~fd"
    )
)

if defined EXE_FILE (
    echo   App folder : !APP_DIR!
    echo   Launcher   : !EXE_FILE!
    echo.
    echo   To run : open the folder and double-click the .exe
    echo            ^(keep the whole folder together when sharing^)
) else (
    echo   Output : %OUT_DIR%  ^(look for the app folder^)
)

echo.
echo ============================================================
echo.

set /p SHORTCUT_CHOICE="Create desktop shortcut? [y/N]: "
if /i "!SHORTCUT_CHOICE!"=="y" (
    if defined EXE_FILE (
        powershell -NoProfile -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%USERPROFILE%\Desktop\InfluencerSeeder.lnk'); $s.TargetPath = '!EXE_FILE!'; $s.WorkingDirectory = '!APP_DIR!'; $s.Description = 'InfluencerSeeder'; $s.Save()"
        echo Desktop shortcut created.
    )
)

echo.
set /p CLEAN_CHOICE="Delete build_tmp folder? [y/N]: "
if /i "!CLEAN_CHOICE!"=="y" (
    rmdir /s /q build_tmp
    echo Cleaned.
)

:: Build succeeded — remove the (now-irrelevant) log.
if exist "%LOGFILE%" del "%LOGFILE%" > nul 2>&1

echo.
echo Press any key to exit.
pause > nul
exit /b 0

:fail
echo.
echo ============================================================
echo [ERROR] Build failed. Last lines of the log:
echo ------------------------------------------------------------
if exist "%LOGFILE%" (
    powershell -NoProfile -Command "Get-Content -LiteralPath '%LOGFILE%' -Tail 60" 2>nul || type "%LOGFILE%"
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

:PYVER_OK
rem  arg1 = "Python X.Y.Z"  ->  exit /b 0 if version is 3.10+, else exit /b 1
set "_NUM="
set "_MAJ="
set "_MIN="
for /f "tokens=2 delims= " %%a in ("%~1") do set "_NUM=%%a"
for /f "tokens=1,2 delims=." %%a in ("!_NUM!") do (
    set "_MAJ=%%a"
    set "_MIN=%%b"
)
if not defined _MIN exit /b 1
if !_MAJ! GTR 3 exit /b 0
if !_MAJ! EQU 3 if !_MIN! GEQ 10 exit /b 0
exit /b 1
