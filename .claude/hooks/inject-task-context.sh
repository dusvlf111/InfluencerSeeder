#!/bin/bash
# SessionStart Hook (compact matcher): 컨텍스트 압축 후 task 상태 재주입
# 컴팩션으로 잃어버린 task 진행 상황을 다시 알려줌

TASK_FILES=$(ls .claude/tasks/todo/*.md 2>/dev/null)

[ -z "$TASK_FILES" ] && exit 0

echo "=== 컨텍스트 재주입: 진행 중인 Task ==="
echo ""

for FILE in $TASK_FILES; do
  REMAINING=$(grep -c "\[ \]" "$FILE" 2>/dev/null | tail -1 || echo 0)
  DONE=$(grep -c "\[x\]" "$FILE" 2>/dev/null | tail -1 || echo 0)
  REMAINING=${REMAINING##*:}
  DONE=${DONE##*:}

  if [ "$REMAINING" -gt 0 ]; then
    echo "📋 파일: $FILE"
    echo "   완료: ${DONE}개 / 남은 작업: ${REMAINING}개"
    echo "   다음 작업:"
    grep "\[ \]" "$FILE" | head -3 | sed 's/^/     /'
    echo ""
  fi
done

if [ -f ".claude/.task-running" ]; then
  echo "⚠️  task-runner가 실행 중입니다. 중단 없이 계속 진행하세요."
fi

echo "=== End ==="
