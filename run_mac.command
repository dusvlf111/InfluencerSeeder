#!/bin/bash
# InfluencerSeeder - Run script (macOS)
# Double-click this file to run the app directly from source.
# (For installation/packaging, use build_mac.sh)

set -euo pipefail

LOG=""
# On any non-zero exit, keep the Terminal open and show where the log is.
_on_exit() {
    code=$?
    if [ "$code" -ne 0 ]; then
        echo ""
        echo "============================================================"
        echo "[ERROR] 문제가 발생했습니다 (종료코드 $code). 위 메시지를 확인하세요."
        [ -n "$LOG" ] && [ -f "$LOG" ] && echo "로그 파일: $LOG"
        echo "============================================================"
        read -r -p "엔터를 누르면 창을 닫습니다..." _
    fi
}
trap _on_exit EXIT

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# This script sits next to src/; the app sources live inside src/.
cd "$SCRIPT_DIR/src"
LOG="$SCRIPT_DIR/run_error.log"
rm -f "$LOG"

echo ""
echo "============================================================"
echo "  InfluencerSeeder - Run (macOS)"
echo "============================================================"
echo ""

# ----- Step 1: Check Python 3 -----
if ! command -v python3 &>/dev/null; then
    osascript -e 'display alert "Python 3 is not installed." message "Please install Python from https://www.python.org and run again."' 2>/dev/null || true
    echo "[ERROR] Python 3 not found. Install it from https://www.python.org and run again."
    exit 1
fi
echo "[1/3] Python: $(python3 --version 2>&1)"

# 수집은 임베디드 QtWebEngine(Chromium 내장)에서 진행 — 시스템 Chrome 불필요.

# ----- Step 2: Virtual environment + dependencies -----
# Reuse the same venv as build_mac.sh (skips fast if it already exists).
VENV_DIR=".venv_mac"
VENV_PY="$VENV_DIR/bin/python"

if [ ! -x "$VENV_PY" ]; then
    echo "[2/3] First run: creating venv and installing dependencies (2-5 min)..."
    python3 -m venv "$VENV_DIR" > "$LOG" 2>&1
    "$VENV_PY" -m pip install --upgrade pip --quiet >> "$LOG" 2>&1
    "$VENV_PY" -m pip install -r requirements.txt --quiet >> "$LOG" 2>&1
else
    if ! "$VENV_PY" -c "import PyQt6; from PyQt6.QtWebEngineWidgets import QWebEngineView" &>/dev/null; then
        echo "[2/3] Installing missing dependencies..."
        "$VENV_PY" -m pip install -r requirements.txt --quiet >> "$LOG" 2>&1
    else
        echo "[2/3] Virtual environment OK."
    fi
fi

# ----- Step 3: Launch app (tee output to the log; a crash leaves it readable) -----
echo "[3/3] Starting app..."
echo ""
"$VENV_PY" main.py 2>&1 | tee "$LOG"

# Normal exit — drop the trap's error handling and clean up.
trap - EXIT
rm -f "$LOG"
