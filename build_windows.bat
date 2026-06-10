@echo off
setlocal enabledelayedexpansion
chcp 65001 > nul 2>&1

:: This script sits next to src\; the app sources live inside src\.
cd /d "%~dp0src"

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
    echo         Please install Python manually from https://www.python.org
    echo         Then re-run this script.
    pause
    exit /b 1
)

echo       Downloading Python 3.12 (this may take a few minutes)...
winget install Python.Python.3.12 --silent --accept-package-agreements --accept-source-agreements
if errorlevel 1 (
    echo [ERROR] Python installation failed.
    echo         Please install manually from https://www.python.org
    pause
    exit /b 1
)

set "PATH=%LOCALAPPDATA%\Programs\Python\Python312;%LOCALAPPDATA%\Programs\Python\Python312\Scripts;%PATH%"

python --version > nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python installed but not found in PATH.
    echo         Please close this window, reopen, and run the script again.
    pause
    exit /b 1
)
set PYTHON_CMD=python
for /f "tokens=*" %%v in ('python --version 2^>^&1') do set PYTHON_VERSION=%%v
echo       Installed: !PYTHON_VERSION!

:PYTHON_OK

:: -------------------------------------------------------
:: Step 1.5: Ensure Google Chrome
::   Selenium launches Chrome at runtime; the NSS libraries
::   (nss3.dll / nspr4.dll — the Windows equivalent of
::   libnss3/libnspr4) ship INSIDE the Chrome install. If Chrome
::   is missing, the built app fails to start the browser.
:: -------------------------------------------------------
echo.
echo [*] Checking Google Chrome...

set "CHROME_FOUND="
if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" set "CHROME_FOUND=1"
if exist "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" set "CHROME_FOUND=1"
if exist "%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe" set "CHROME_FOUND=1"

if defined CHROME_FOUND (
    echo       Found Google Chrome.
    goto :CHROME_OK
)
echo       Chrome not found. Installing via winget...
winget --version > nul 2>&1
if errorlevel 1 (
    echo [WARN] winget unavailable. Install Chrome from https://www.google.com/chrome/
    goto :CHROME_OK
)
winget install Google.Chrome --silent --accept-package-agreements --accept-source-agreements
if errorlevel 1 echo [WARN] Chrome install failed. Install from https://www.google.com/chrome/
:CHROME_OK

:: -------------------------------------------------------
:: Step 2: Create virtual environment
:: -------------------------------------------------------
echo.
echo [2/5] Setting up virtual environment...
if exist ".venv_win\Scripts\python.exe" (
    echo       .venv_win already exists, skipping.
) else (
    !PYTHON_CMD! -m venv .venv_win
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
    echo       Created .venv_win
)

set VENV_PY=.venv_win\Scripts\python.exe

:: -------------------------------------------------------
:: Step 3: Install packages
:: -------------------------------------------------------
echo.
echo [3/5] Installing packages (first run takes 2-5 minutes)...
echo       Packages: PyQt6, selenium, webdriver-manager, pyinstaller
echo.

%VENV_PY% -m pip install --upgrade pip --quiet --no-warn-script-location

set PKG_COUNT=0
for %%p in (PyQt6 selenium webdriver-manager pyinstaller) do (
    set /a PKG_COUNT+=1
    echo       [!PKG_COUNT!/6] Installing %%p...
    %VENV_PY% -m pip install %%p --quiet --no-warn-script-location
    if errorlevel 1 (
        echo [ERROR] Failed to install %%p
        pause
        exit /b 1
    )
)
echo       All packages installed.

:: -------------------------------------------------------
:: Step 4: Build EXE
:: -------------------------------------------------------
echo.
echo [4/5] Building EXE with PyInstaller (2-5 minutes)...
echo.

if exist "build_tmp" rmdir /s /q build_tmp

:: Output the app next to src\ (project root = this script's folder).
pushd "%~dp0"
set "OUT_DIR=%CD%"
popd

%VENV_PY% -m PyInstaller build.spec --distpath "%OUT_DIR%" --workpath build_tmp --noconfirm
if errorlevel 1 (
    echo.
    echo [ERROR] Build failed. See output above for details.
    pause
    exit /b 1
)

:: -------------------------------------------------------
:: Step 5: Done
:: -------------------------------------------------------
echo.
echo [5/5] Build complete!
echo.
echo ============================================================
echo.

set "EXE_FILE="
for %%f in ("%OUT_DIR%\*.exe") do set "EXE_FILE=%%~ff"

if defined EXE_FILE (
    echo   Output : !EXE_FILE!
    echo.
    echo   To run : Double-click  !EXE_FILE!
) else (
    echo   Output : %OUT_DIR%
    echo   To run : Double-click the .exe in that folder
)

echo.
echo ============================================================
echo.

set /p SHORTCUT_CHOICE="Create desktop shortcut? [y/N]: "
if /i "!SHORTCUT_CHOICE!"=="y" (
    if defined EXE_FILE (
        powershell -NoProfile -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%USERPROFILE%\Desktop\InfluencerSeeder.lnk'); $s.TargetPath = '!EXE_FILE!'; $s.WorkingDirectory = '%OUT_DIR%'; $s.Description = 'InfluencerSeeder'; $s.Save()"
        echo Desktop shortcut created.
    )
)

echo.
set /p CLEAN_CHOICE="Delete build_tmp folder? [y/N]: "
if /i "!CLEAN_CHOICE!"=="y" (
    rmdir /s /q build_tmp
    echo Cleaned.
)

echo.
echo Press any key to exit.
pause > nul
