#!/bin/bash
# PostToolUse Hook: Python 파일 포맷팅 자동 실행
# Edit/Write로 .py 파일 수정 시 ruff/black이 설치돼 있으면 자동 포맷.
# 없으면 조용히 통과 (no-op). 절대 실패로 작업을 막지 않는다.

INPUT=$(cat)
# JSON 파싱: jq가 있으면 jq, 없으면 python3 (이 환경엔 python3만 있음)
if command -v jq >/dev/null 2>&1; then
  FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')
else
  FILE_PATH=$(echo "$INPUT" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("tool_input",{}).get("file_path",""))' 2>/dev/null)
fi

[ -z "$FILE_PATH" ] && exit 0
[ ! -f "$FILE_PATH" ] && exit 0

# .py 파일만 처리
case "$FILE_PATH" in
  *.py) ;;
  *) exit 0 ;;
esac

# venv 우선, 없으면 PATH 상의 도구 사용
VENV_BIN="src/.venv/bin"

run_fmt() {
  local tool="$1"; shift
  if [ -x "$VENV_BIN/$tool" ]; then
    "$VENV_BIN/$tool" "$@" 2>/dev/null || true
  elif command -v "$tool" >/dev/null 2>&1; then
    "$tool" "$@" 2>/dev/null || true
  fi
}

# ruff(린트+포맷) → black 순으로 시도 (있는 것만)
run_fmt ruff check --fix "$FILE_PATH"
run_fmt ruff format "$FILE_PATH"
run_fmt black "$FILE_PATH"

exit 0
