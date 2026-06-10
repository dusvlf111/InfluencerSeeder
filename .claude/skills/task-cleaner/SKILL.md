---
name: task-cleaner
description: "완료된 task 파일과 관련 자료(PRD, 스크린샷 등)를 기능명 폴더로 정리하여 done/에 아카이브합니다. 사용자가 'task 정리', '작업 정리', '태스크 정리', '파일 정리해줘', 'clean tasks' 등을 요청할 때 사용합니다."
argument-hint: "[feature-name]"
disable-model-invocation: true
user-invocable: true
---

# Task Cleaner — 작업 파일 정리

완료된 task 파일, PRD, 스크린샷을 `.claude/tasks/done/` 하위의 **기능명 폴더**로 정리한다.

---

## 폴더 구조

```
.claude/tasks/
├── todo/                     ← 진행 중인 task
├── done/
│   ├── {기능명}/
│   │   ├── prd-*.md
│   │   ├── tasks-*-push1.md
│   │   ├── result-*-push1.md
│   │   └── *.png
│   └── {다른 기능}/
└── (루트에는 현재 진행 중인 파일만)
```

---

## 정리 프로세스

### 1. 폴더 이름 결정
우선순위:
1. 사용자가 인자로 지정한 이름 → 그대로 사용.
2. 현재 Git 브랜치명 → `git branch --show-current` (repo일 때만).
3. task/PRD 파일명에서 추출 → `prd-260610-3.md` 관련이면 기능 요지로 명명 (예: `stealth-resume-v3`).

repo가 아니거나 브랜치가 없으면 PRD 내용 기반으로 제안하고 확인받는다.

### 2. 정리 대상 식별
```bash
ls -1 .claude/tasks/*.{md,png,jpg,csv,pdf} 2>/dev/null
ls -1 .claude/tasks/todo/*.md 2>/dev/null   # 모든 체크박스 [x]인 것
```

| 파일 종류 | 정리 조건 |
|-----------|-----------|
| `tasks-*.md` (todo/) | 모든 체크박스가 `[x]` |
| `prd*.md` | 관련 task가 모두 완료 |
| `result-*.md` | 완료된 결과보고서 |
| `*.png`, `*.jpg` | 관련 task/PRD와 함께 이동 |

### 3. 파일 이동
```bash
mkdir -p .claude/tasks/done/{폴더명}
mv .claude/tasks/{대상} .claude/tasks/done/{폴더명}/
mv .claude/tasks/todo/{완료파일} .claude/tasks/done/{폴더명}/
```

### 4. 정리 보고
```
✅ 정리 완료: done/{폴더명}/
이동된 파일:
- prd-260610-3.md
- tasks-...-push1.md (완료)
- 스크린샷 6장
```

---

## 규칙

- `todo/`에 미완료(`[ ]` 남은) task는 **이동하지 않음**.
- `done/` 내 이름 충돌 시 덮어쓰지 않고 사용자 확인.
- `todo/`, `done/` 디렉토리 자체는 삭제하지 않음.
- PRD와 관련 스크린샷은 같은 폴더에 함께 이동.
- 정리 후 `tasks/` 루트와 `todo/`가 깔끔한지 확인.
- **주의:** 아직 작업 중인 현재 PRD(`prd-260610-3.md` 등)는 관련 task가 미완료면 옮기지 않는다.
