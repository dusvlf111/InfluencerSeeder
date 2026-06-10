---
name: task-runner
description: "todo/ 폴더의 task 파일을 읽고 task-executor 에이전트에 위임하여 자동 실행합니다. 사용자가 '작업 실행', '태스크 실행', '다음 작업', '작업 계속', '이어서 진행' 등을 요청할 때 사용합니다."
argument-hint: "[task-file-path]"
disable-model-invocation: true
user-invocable: true
---

# Task Runner — 오케스트레이터

`.claude/tasks/todo/` 의 task 파일을 읽고 `task-executor` 에이전트에 실행을 위임한다.
실제 코드 작성·테스트·커밋은 에이전트가 담당한다.

> **핵심:** `task-executor`는 Skill/Agent 도구가 없다.
> task 파일 내에 모든 컨텍스트(규칙·문서·이미지 경로)가 이미 포함되어 있어야 한다.
> `task-maker`가 올바르게 생성했다면 추가 주입은 불필요하다.

---

## 시작 절차

```bash
# 1. sentinel 파일 생성 (Stop 훅이 이걸 보고 중단 방지)
touch .claude/.task-running

# 2. done/ 디렉토리 확인
mkdir -p .claude/tasks/done
```

파일이 지정되지 않으면 `todo/` 의 `tasks-*.md` 목록을 보여주고 선택 요청
(이 경우에만 사용자에게 질문 허용 — 이후는 완전 자율).

---

## 실행 루프

```
todo/ 에서 미완료 task 파일 로드
  ↓
task 파일의 컨텍스트 완전성 검증 (아래 체크리스트)
  ↓
task-executor 에이전트에 위임 (전체 파일 내용 + 지시사항 전달)
  ↓
에이전트 완료 보고 수신
  ↓
Push 파일 완료 확인 → done/ 이동 + 결과보고서 작성
  ↓
다음 todo/ 파일 있으면 → 자동으로 계속 (질문 금지)
  ↓
모든 파일 완료 → sentinel 삭제 → 최종 보고
```

---

## 컨텍스트 완전성 검증

task 파일을 에이전트에 넘기기 전 확인. 누락 시 **task 파일에 직접 추가 후** 위임한다.

### 체크리스트
- [ ] `### 실행 환경` 섹션 존재 (사용 가능/불가 도구 + pytest 명령)
- [ ] `### 참조 문서` 섹션 존재 (Read로 읽을 경로)
- [ ] `### 적용 규칙` 섹션 존재 (프로젝트 컨벤션 요약)
- [ ] `### 관련 파일` 섹션 존재 (수정 대상)
- [ ] 이미지 참조 필요 시 `### 참조 이미지` 섹션 존재

### 자동 보강
1. **참조 문서 누락** → PRD를 읽고 `src/CLAUDE.md` 및 관련 모듈 경로 추가.
2. **적용 규칙 누락** → `src/CLAUDE.md`를 읽고 핵심 규칙(신호/슬롯·디자인토큰·스토리지·테스트격리) 요약 삽입.
3. **참조 이미지 누락** → PRD에 이미지 경로 있으면 추가.
4. **실행 환경 누락** → 아래 블록 삽입:

   ```markdown
   ### 실행 환경
   - **사용 가능 도구:** Read, Write, Edit, Bash, Glob, Grep, Task
   - **사용 불가 도구:** Skill, Agent
   - **테스트:** `cd src && .venv/bin/pytest tests/ -v`
   - **이미지 읽기:** Read로 .png 직접 열람 가능
   ```

---

## 에이전트 위임 방법

각 Push 파일마다 `task-executor` 에이전트에 위임:

```
task-executor 에이전트를 사용하여 다음 task 파일을 실행하세요:

파일: .claude/tasks/todo/tasks-[name]-push[N].md
내용: [파일 전체 내용]

지시사항:
- 작업 시작 전 "참조 문서" 섹션의 모든 문서를 Read로 읽을 것
- "참조 이미지"가 있으면 Read로 열어 UI/위치 참고할 것
- "적용 규칙"(신호/슬롯, 디자인토큰, 스토리지, 테스트 격리)을 준수할 것
- 모든 미완료([ ]) 작업을 순서대로 실행
- 각 하위 작업 완료 시 즉시 커밋
- 모든 작업 완료 시 (원격 있으면) git push
- 완료 항목은 [x] 로 체크
- 오류 시 T3 수정 작업 추가 후 자동 해결
```

---

## Push 파일 완료 처리

모든 항목이 [x] 된 후:

```bash
mv .claude/tasks/todo/tasks-[name]-pushN.md .claude/tasks/done/
```

결과보고서(`done/result-[name]-pushN.md`) 생성:

```markdown
# 결과보고서: [파일명]

> 완료일: [날짜]
> Push 범위: [기능 요약]

## 구현 요약
| 작업 | 상태 | 커밋 |
|------|------|------|
| 1.1 [작업명] | ✅ | `해시` |

## 생성/수정 파일
- `src/...` - [변경 내용]

## 테스트 결과
- pytest 통과: N개

## 이슈 및 특이사항
- [발생 오류 및 해결법]
```

---

## 종료 처리

```bash
rm -f .claude/.task-running
```

이후 Stop 훅이 중단을 허용하고, 최종 보고 후 종료.

---

## 주의 (이 프로젝트 특성)

- 테스트는 `src/.venv/bin/pytest` 사용 (가상환경 격리). 루트가 아니라 `src/`에서 실행.
- Selenium/브라우저 실제 구동은 테스트에서 하지 않음 (전부 mock). 에이전트가 실제 인스타 접속을 시도하면 안 됨.
- `git`은 이 프로젝트가 아직 repo가 아닐 수 있음 — `git status` 실패 시 커밋 단계를 건너뛰고 파일 저장만 진행, 보고에 명시.
