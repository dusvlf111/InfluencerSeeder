#!/bin/bash
# 인플루언서 시딩기 시작 스크립트 (macOS)
# 이 파일을 더블클릭하면 자동으로 실행됩니다.

cd "$(dirname "$0")"

# Python3 설치 확인
if ! command -v python3 &>/dev/null; then
    osascript -e 'display alert "Python3가 설치되어 있지 않습니다." message "https://www.python.org 에서 Python을 설치해주세요."'
    exit 1
fi

# 의존성 설치 (이미 설치된 경우 빠르게 통과)
echo "의존성 확인 중..."
python3 -m pip install -r requirements.txt --quiet

# 앱 실행
echo "앱 시작..."
python3 main.py
