---
name: task-maker
description: "PRD나 요구사항을 기반으로 Git 워크플로우에 맞는 작업 목록을 생성합니다. 사용자가 'PRD 기반 작업 만들어줘', '작업 목록 생성', 'task 만들어줘', '기능 분해해줘' 등을 요청할 때 사용합니다. InfluencerSeeder(PyQt6/Selenium/CSV) 프로젝트 컨벤션에 맞춰 분해합니다."
argument-hint: "[prd-file-path]"
disable-model-invocation: true
user-invocable: true
---

# PRD 기반 작업 목록 생성

PRD를 분석하여 **Push 단위 파일 분리** + **커밋 단위 하위 작업** 구조로 task 파일을 생성한다.

> **핵심 원칙:** `task-executor` 서브에이전트는 `Skill` 도구가 없다.
> 따라서 task 파일에 스킬/규칙 내용을 직접 요약하고, 참조 문서·이미지 경로를 명시해야 한다.
> 서브에이전트가 `Read`로 직접 읽도록 **프로젝트 루트 기준 경로**를 사용한다.
>
> **이 프로젝트는 Python/PyQt6 + pytest** 다. React/Vercel 규칙은 적용하지 않는다.

---

## 폴더 구조

```
.claude/tasks/
  prd-*.md                          ← PRD (prd-maker 산출물)
  todo/
    tasks-[prd-name]-push1.md
    tasks-[prd-name]-push2.md
    task-[YYMMDD].md                ← 마스터 인덱스
  done/
    tasks-[prd-name]-push1.md
    result-[prd-name]-push1.md
```

`todo/`, `done/` 없으면 자동 생성.

---

## 생성 프로세스 (확인 없이 자동 완료)

### 1. PRD 분석
- 인자로 받은 파일 읽기 (없으면 `.claude/tasks/` 에서 최신 `prd-*.md` 탐색).
- 기능 요구사항(FR), 데이터 스키마, 코드 변경 가이드, 테스트 계획 전체 파악.
- **PRD에 참조된 이미지/스크린샷 경로 수집** (`.claude/tasks/*.png`).
- **PRD가 참조하는 코드/문서 경로 수집** (`src/CLAUDE.md`, `src/core/*`, `src/ui/*` 등).

### 2. Push 단위 파일 분리

각 Push = **별도 파일** (`todo/tasks-[prd-name]-push[N].md`):
- 독립적으로 실행/테스트 가능한 기능 단위 (예: "스토리지 CSV 분리", "스크래퍼 stealth/resume", "설정 UI 6탭 재편").
- 하위 커밋 3~7개.
- 의존 순서가 있으면 push 번호로 표현 (push1 완료 후 push2).

### 3. 커밋 단위 하위 작업

각 하위 작업 = **하나의 Git 커밋**:
- 파일 수정 5개 미만.
- 독립적으로 pytest 검증 가능.

### 4. 테스트 작업 자동 추가

모든 구현 작업 뒤에 자동 추가:
- `[N].T1` pytest 테스트 코드 작성 (`tests/test_<모듈>.py`)
- `[N].T2` `.venv/bin/pytest tests/test_<모듈>.py -v` 실행 및 검증

### 5. 컨텍스트 수집 및 임베딩

각 Push 파일에 서브에이전트가 필요로 하는 **모든 컨텍스트를 직접 포함**한다.

#### 5-1. 참조 이미지
PRD에 스크린샷이 있으면 실제 경로 + 용도 + 관련 작업번호를 표로:

```markdown
### 참조 이미지

| 이미지 | 용도 | 관련 작업 |
|--------|------|-----------|
| `.claude/tasks/1_돋보기 클릭.png` | Step1 검색 아이콘 위치 | 2.1 |
| `.claude/tasks/5_게시물에서 프로필 클릭.png` | Step5 프로필 링크 위치 | 2.4 |
```

#### 5-2. 참조 문서/코드
작업 전 반드시 읽을 파일:

```markdown
### 참조 문서

작업 시작 전 반드시 아래를 `Read`로 읽을 것:

| 문서 | 용도 |
|------|------|
| `src/CLAUDE.md` | 신호/슬롯·디자인토큰·스토리지·테스트 격리 규칙 |
| `src/core/storage.py` | 기존 CSV 로드/저장 패턴 (수정 대상) |
| `src/core/scraper.py` | ScraperThread 구조·신호 (수정 대상) |
```

#### 5-3. 적용 규칙 임베딩 (프로젝트 컨벤션 요약)
서브에이전트는 Skill 도구가 없으므로 **이 프로젝트 핵심 규칙을 task 파일에 직접 요약**한다.
`src/CLAUDE.md`를 읽고 해당 Push에 필요한 규칙만 발췌:

```markdown
### 적용 규칙 (프로젝트 컨벤션)

#### 신호/슬롯 (UI 안전성)
- `ScraperThread`는 UI를 직접 조작하지 않는다. `log_signal`/`progress_signal`/
  `result_signal`/`done_signal`/`step_signal` 등 signal emit으로만 통신.
- `QThread.run()` 내부에서 위젯 직접 호출 금지.

#### 디자인 토큰
- 색상은 `design/tokens.py`의 `Colors.*`만 사용. QSS 리터럴에 hex 직접 금지.

#### 스토리지
- 파일 I/O는 `core/storage.py`에만. 함수 추가 시 `DATA_DIR` 기준 경로 사용.
- CSV 파일 없으면 첫 load 시 기본값을 기록 후 반환.

#### 테스트 격리 (pytest)
- `storage` 테스트: `monkeypatch.setattr(storage, "DATA_DIR", tmp_path)`.
- Selenium 드라이버: `unittest.mock.MagicMock()` 으로 대체.
- 실제 네트워크/브라우저 호출 금지 — 전부 mock.
```

> ⚠️ 절대 "code-quality 스킬 적용" 처럼 스킬명만 적지 말 것. **규칙 본문을 요약**해 넣는다.

#### 5-4. 실행 환경 (서브에이전트 제약)

```markdown
### 실행 환경

- **사용 가능 도구:** Read, Write, Edit, Bash, Glob, Grep, Task
- **사용 불가 도구:** Skill, Agent (서브에이전트 중첩 불가)
- **이미지 읽기:** Read 도구로 .png/.jpg 직접 열람 가능
- **테스트 실행:** `cd src && .venv/bin/pytest tests/ -v`
- **실행:** `cd src && .venv/bin/python main.py`
- **병렬 작업:** 불가 (순차 실행)
```

### 6. 마스터 인덱스 파일 생성

`todo/task-[YYMMDD].md` 생성:
- Push 목록 테이블 (파일명, 범위, 상태).
- 전체 참조 문서/이미지 경로 목록.
- 프로젝트 컨벤션 핵심 요약.

---

## 출력 형식 (Push 파일)

```markdown
# Tasks: [PRD명] - Push [N]

> PRD: `.claude/tasks/[prd-파일].md`
> Push 범위: [기능 요약]
> 상태: 🔲 진행 중

---

### 실행 환경

- **사용 가능 도구:** Read, Write, Edit, Bash, Glob, Grep, Task
- **사용 불가 도구:** Skill, Agent
- **테스트:** `cd src && .venv/bin/pytest tests/ -v`
- **이미지 읽기:** Read로 .png 직접 열람 가능

### 참조 이미지

| 이미지 | 용도 | 관련 작업 |
|--------|------|-----------|
| `경로` | 설명 | 작업번호 |

### 참조 문서

작업 시작 전 반드시 `Read`로 읽을 것:

| 문서 | 용도 |
|------|------|
| `src/CLAUDE.md` | 프로젝트 규칙 |

### 적용 규칙 (프로젝트 컨벤션)

[해당 Push에 필요한 규칙만 발췌 — 5-3 참조]

### 관련 파일

- `src/core/storage.py` - CSV 스토리지 (수정 대상)
- `src/core/scraper.py` - ScraperThread (수정 대상)
- `src/tests/test_storage.py` - 테스트 (추가 대상)

---

## 작업

- [ ] 1.0 상위 작업 (Push 범위)
    - [ ] 1.1 하위 작업 (커밋 단위)
        **작업 상세:** [구체적 구현 내용 — 함수 시그니처/CSV 컬럼 수준]
        **참조:** 이미지 `경로`, 문서 `경로`
        - [ ] 1.1.T1 pytest 테스트 작성 (`tests/test_xxx.py`)
        - [ ] 1.1.T2 테스트 실행 및 검증
    - [ ] 1.2 하위 작업 (커밋 단위)
        **작업 상세:** [...]
        - [ ] 1.2.T1 pytest 테스트 작성
        - [ ] 1.2.T2 테스트 실행 및 검증
```

---

## 규칙

- 사용자 확인 없이 분석 → 파일 저장까지 자동 완료.
- 반드시 Push 단위로 파일 분리 (단일 파일 금지).
- 각 Push 파일에 적용할 **프로젝트 컨벤션을 요약**하여 임베딩 (스킬명만 기재 금지).
- 참조 문서(`src/CLAUDE.md`, `src/core/*`, `src/ui/*`) 경로 명시 + "Read로 읽을 것" 지시.
- 참조 이미지가 있으면 **실제 경로 + 용도 + 관련 작업번호** 명시.
- 서브에이전트 제약(사용 가능/불가 도구)을 task 파일 상단에 명시.
- 모든 구현 작업에 pytest T1/T2 자동 추가.
- 완료 후 생성된 파일 목록만 간단히 보고.

## 참고 자료

- 프로젝트 규칙: `src/CLAUDE.md`
- 코드: `src/core/*.py`, `src/ui/**/*.py`, `src/design/*.py`
- 테스트 작성 규칙: `.claude/commands/write-tests.md`
- 실행 에이전트: `.claude/agents/task-executor.md`
