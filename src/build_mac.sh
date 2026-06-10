#!/bin/bash
set -euo pipefail

# ----- spinner helpers -----
_spin_pid=
_start_spinner() {
    local msg="$1"
    (
        i=0
        while true; do
            c=$(( i % 4 ))
            case $c in 0) ch='|';; 1) ch='/';; 2) ch='-';; 3) ch='\\';; esac
            printf "\r      [%s] %s   " "$ch" "$msg"
            i=$(( i + 1 ))
            sleep 0.1
        done
    ) &
    _spin_pid=$!
    disown "$_spin_pid" 2>/dev/null || true
}
_stop_spinner() {
    if [ -n "$_spin_pid" ]; then
        kill "$_spin_pid" 2>/dev/null || true
        wait "$_spin_pid" 2>/dev/null || true
        _spin_pid=
    fi
    printf "\r%-70s\n" "      done."
}

echo ""
echo "============================================================"
echo "  InfluencerSeeder - macOS Build Script"
echo "============================================================"
echo ""

# ----- Step 1: Check Python 3 -----
echo "[1/5] Checking Python 3..."

PYTHON_CMD=""

if command -v python3 &>/dev/null; then
    PYTHON_CMD="python3"
    echo "      Found: $(python3 --version 2>&1)"
else
    echo "      Python 3 not found. Installing via Homebrew..."

    if ! command -v brew &>/dev/null; then
        echo "      Homebrew not found. Installing Homebrew..."
        _start_spinner "Installing Homebrew"
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)" \
            </dev/null > /tmp/brew_install.log 2>&1 || {
            _stop_spinner
            echo "[ERROR] Homebrew install failed. See /tmp/brew_install.log"
            echo "        Or install manually from https://brew.sh"
            exit 1
        }
        _stop_spinner
        if [ -f "/opt/homebrew/bin/brew" ]; then
            eval "$(/opt/homebrew/bin/brew shellenv)"
        elif [ -f "/usr/local/bin/brew" ]; then
            eval "$(/usr/local/bin/brew shellenv)"
        fi
    fi

    _start_spinner "Installing Python 3.12"
    brew install python@3.12 > /tmp/python_install.log 2>&1 || {
        _stop_spinner
        echo "[ERROR] Python install failed. See /tmp/python_install.log"
        exit 1
    }
    _stop_spinner

    export PATH="$(brew --prefix python@3.12)/bin:$PATH"

    if ! command -v python3 &>/dev/null; then
        echo "[ERROR] python3 not found after install."
        echo "        Please restart your terminal and re-run this script."
        exit 1
    fi
    PYTHON_CMD="python3"
    echo "      Installed: $(python3 --version 2>&1)"
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ----- Ensure Google Chrome -----
# Selenium launches Chrome at runtime. On macOS the NSS libraries are bundled
# inside Google Chrome.app, so they can't go missing as long as Chrome exists.
echo ""
echo "[*] Checking Google Chrome..."
if [ -d "/Applications/Google Chrome.app" ] || [ -d "$HOME/Applications/Google Chrome.app" ]; then
    echo "      Found Google Chrome."
elif command -v brew &>/dev/null; then
    echo "      Chrome not found. Installing via Homebrew cask..."
    if brew install --cask google-chrome > /tmp/chrome_install.log 2>&1; then
        echo "      Chrome installed."
    else
        echo "      [WARN] Chrome install failed (see /tmp/chrome_install.log)."
        echo "             Install manually from https://www.google.com/chrome/"
    fi
else
    echo "      [WARN] Chrome not found and Homebrew unavailable."
    echo "             Install Chrome manually from https://www.google.com/chrome/"
fi

# ----- Step 2: Virtual environment -----
echo ""
echo "[2/5] Setting up virtual environment..."

VENV_DIR=".venv_mac"
if [ -f "$VENV_DIR/bin/python" ]; then
    echo "      $VENV_DIR already exists, skipping."
else
    _start_spinner "Creating $VENV_DIR"
    $PYTHON_CMD -m venv "$VENV_DIR" > /tmp/venv_create.log 2>&1 || {
        _stop_spinner
        echo "[ERROR] Failed to create venv. See /tmp/venv_create.log"
        exit 1
    }
    _stop_spinner
fi

VENV_PY="$VENV_DIR/bin/python"

# ----- Step 3: Install packages -----
echo ""
echo "[3/5] Installing packages (first run: 2-5 minutes)..."

PACKAGES=("PyQt6" "selenium" "webdriver-manager" "pyinstaller")
TOTAL=${#PACKAGES[@]}

_start_spinner "Upgrading pip"
$VENV_PY -m pip install --upgrade pip > /tmp/pip_install.log 2>&1 || true
_stop_spinner

for i in "${!PACKAGES[@]}"; do
    PKG="${PACKAGES[$i]}"
    NUM=$(( i + 1 ))
    _start_spinner "[$NUM/$TOTAL] $PKG"
    $VENV_PY -m pip install "$PKG" --quiet >> /tmp/pip_install.log 2>&1 || {
        _stop_spinner
        echo "[ERROR] Failed to install $PKG. See /tmp/pip_install.log"
        exit 1
    }
    _stop_spinner
done
echo "      All packages installed."

# ----- Step 4: Build .app -----
echo ""
echo "[4/5] Building .app with PyInstaller (3-8 minutes)..."
echo ""

rm -rf build_tmp

_start_spinner "Running PyInstaller"
$VENV_PY -m PyInstaller build.spec \
    --distpath dist \
    --workpath build_tmp \
    --noconfirm \
    > /tmp/pyinstaller.log 2>&1 || {
    _stop_spinner
    echo "[ERROR] Build failed. Last 30 lines:"
    tail -30 /tmp/pyinstaller.log
    exit 1
}
_stop_spinner

APP_PATH=""
for f in dist/*.app; do
    [ -d "$f" ] && APP_PATH="$f" && break
done

if [ -z "$APP_PATH" ]; then
    echo "[ERROR] No .app found in dist/"
    ls -la dist/ 2>/dev/null || true
    exit 1
fi
APP_NAME="$(basename "$APP_PATH")"

xattr -cr "$APP_PATH" 2>/dev/null || true

# ----- Step 5: Create DMG -----
echo ""
echo "[5/5] Creating DMG for distribution..."

DMG_NAME="InfluencerSeeder.dmg"
_start_spinner "Creating $DMG_NAME"
hdiutil create \
    -volname "InfluencerSeeder" \
    -srcfolder "$APP_PATH" \
    -ov \
    -format UDZO \
    "dist/$DMG_NAME" \
    >> /tmp/pyinstaller.log 2>&1 && _stop_spinner || {
    _stop_spinner
    echo "      (DMG skipped - .app can be distributed directly)"
    DMG_NAME=""
}

# ----- Done -----
echo ""
echo "============================================================"
echo "  Build complete!"
echo ""
echo "  App    : $SCRIPT_DIR/$APP_PATH"
if [ -n "$DMG_NAME" ]; then
    echo "  DMG    : $SCRIPT_DIR/dist/$DMG_NAME  (share this)"
fi
echo ""
echo "  To run :"
echo "    open \"$APP_PATH\""
echo ""
echo "  Note: If macOS blocks the app (unidentified developer):"
echo "    xattr -cr \"$APP_PATH\""
echo "    open \"$APP_PATH\""
echo "============================================================"
echo ""

read -r -p "Open dist/ in Finder? [y/N]: " OPEN_CHOICE
if [[ "${OPEN_CHOICE,,}" == "y" ]]; then
    open dist/
fi

read -r -p "Create desktop shortcut (.command)? [y/N]: " SHORTCUT_CHOICE
if [[ "${SHORTCUT_CHOICE,,}" == "y" ]]; then
    SHORTCUT="$HOME/Desktop/InfluencerSeeder.command"
    printf '#!/bin/bash\nopen "%s/%s"\n' "$(pwd)" "$APP_PATH" > "$SHORTCUT"
    chmod +x "$SHORTCUT"
    xattr -d com.apple.quarantine "$SHORTCUT" 2>/dev/null || true
    echo "Shortcut created: $SHORTCUT"
fi
