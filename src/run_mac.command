#!/bin/bash
# InfluencerSeeder - Run script (macOS)
# Double-click this file to run the app directly from source.
# (For installation/packaging, use build_mac.sh)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo ""
echo "============================================================"
echo "  InfluencerSeeder - Run (macOS)"
echo "============================================================"
echo ""

# ----- Step 1: Check Python 3 -----
if ! command -v python3 &>/dev/null; then
    osascript -e 'display alert "Python 3 is not installed." message "Please install Python from https://www.python.org and run again."' 2>/dev/null || true
    echo "[ERROR] Python 3 not found. Install it from https://www.python.org and run again."
    read -r -p "Press Enter to exit..." _
    exit 1
fi
echo "[1/3] Python: $(python3 --version 2>&1)"

# ----- Ensure Google Chrome (Selenium launches it; NSS is bundled in Chrome.app) -----
if [ ! -d "/Applications/Google Chrome.app" ] && [ ! -d "$HOME/Applications/Google Chrome.app" ]; then
    if command -v brew &>/dev/null; then
        echo "      Chrome not found. Installing via Homebrew cask..."
        brew install --cask google-chrome > /tmp/chrome_install.log 2>&1 \
            || echo "      [WARN] Chrome install failed. Install from https://www.google.com/chrome/"
    else
        echo "      [WARN] Chrome not found. Install from https://www.google.com/chrome/"
    fi
fi

# ----- Step 2: Virtual environment + dependencies -----
# Reuse the same venv as build_mac.sh (skips fast if it already exists).
VENV_DIR=".venv_mac"
VENV_PY="$VENV_DIR/bin/python"

if [ ! -x "$VENV_PY" ]; then
    echo "[2/3] First run: creating venv and installing dependencies (2-5 min)..."
    python3 -m venv "$VENV_DIR"
    "$VENV_PY" -m pip install --upgrade pip --quiet
    "$VENV_PY" -m pip install -r requirements.txt --quiet
else
    # venv exists but packages may be missing - quick check, then top up.
    if ! "$VENV_PY" -c "import PyQt6, selenium, webdriver_manager" &>/dev/null; then
        echo "[2/3] Installing missing dependencies..."
        "$VENV_PY" -m pip install -r requirements.txt --quiet
    else
        echo "[2/3] Virtual environment OK."
    fi
fi

# ----- Step 3: Launch app -----
echo "[3/3] Starting app..."
echo ""
"$VENV_PY" main.py
