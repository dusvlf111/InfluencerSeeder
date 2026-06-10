# Tasks: InfluencerSeeder v3 - Push 4 (메인윈도우 트레이/이어하기/차단모달 + 영속 로깅 + 진행표시)

> PRD: `.claude/tasks/prd-260610-3.md` (§4 트레이, §7 Resume, §8 로깅/진행표시, §9 `ui/main_window.py`)
> Push 범위: `ui/main_window.py` 시스템 트레이 최소화 + [이어하기] + 차단 모달, `core/logging` 영속 로그 파일, 진행표시 라벨, 신규 신호 배선
> 상태: 🔲 진행 중
> 선행: **Push 1·2 완료 필수** (storage `load_state/clear_state`, scraper `skip_signal/blocked_signal`, 생성자 web/delays/flow/target 주입). Push 3 과도 신호 연계(`imported`, `selector_test_requested`).

---

### 실행 환경

- **사용 가능 도구:** Read, Write, Edit, Bash, Glob, Grep, Task
- **사용 불가 도구:** Skill, Agent
- **테스트 실행:** `cd src && .venv/bin/pytest tests/test_run_logger.py tests/test_main_window.py -v`
- **전체 테스트:** `cd src && .venv/bin/pytest tests/ -v`
- **앱 실행(수동 확인):** `cd src && .venv/bin/python main.py`
- **병렬 작업:** 불가
- ⚠️ pytest-qt 미설치 — `QApplication` 공유 fixture 로 위젯 생성, 순수 로직 위주 검증. 트레이/모달은 메서드 직접 호출로 테스트(`.show()`/event loop 금지).

### 참조 이미지

| 이미지 | 용도 | 관련 작업 |
|--------|------|-----------|
| (이 Push 는 인스타 화면 이미지 직접 참조 없음 — 진행표시/트레이 UI) | — | — |

### 참조 문서

작업 시작 전 반드시 `Read`로 읽을 것:

| 문서 | 용도 |
|------|------|
| `.claude/tasks/prd-260610-3.md` | §4 트레이/절전방지, §7 Resume, §8 영속 로그 포맷·진행표시 |
| `src/ui/main_window.py` | MainWindow 신호 배선·`_start_scrape`·`closeEvent` (수정 대상) |
| `src/core/scraper.py` | Push2 신규 신호(`skip_signal/blocked_signal`)·생성자 시그니처 (배선 대상) |
| `src/core/storage.py` | Push1 `load_state/clear_state/load_web/load_flow/...` (이어하기·주입) |
| `src/ui/panels/results_panel.py` | 로그/진행바 표시 위젯(`append_log`/`update_progress`/`set_status`) — 진행표시 확장 대상 |
| `src/ui/panels/control_panel.py` | [시작]/[이어하기] 버튼·`start_requested` params 구성 |
| `src/design/tokens.py` | 로그 색상(step=accent, info=muted, warning=amber, error=red) 토큰 |

### 적용 규칙 (프로젝트 컨벤션)

#### 신호/슬롯 (UI 안전성)
- `ScraperThread` 신호를 메인스레드 슬롯에 연결해서만 UI 갱신. 워커 스레드에서 위젯 직접 조작 금지.
- 신규 신호 배선: `skip_signal(str)` → 중복 skip 카운트/로그, `blocked_signal()` → 모달 경고 + 일시정지.
- 기존 배선(`log_signal/progress_signal/result_signal/done_signal/error_signal/waiting_login_signal/step_signal`) 유지.

#### 디자인 토큰
- 로그 색상은 `design/tokens.py` `Colors`(step=`accent`, info=`muted2`, warning=`amber`, error=`red`)만 사용. hex 직접 금지.

#### 스토리지 경유
- 영속 로그 파일 경로는 `storage.DATA_DIR / "logs" / "run-YYYYMMDD-HHMMSS.log"`. 로그 파일 생성/기록 헬퍼는 `core/run_logger.py`(신규 모듈) 또는 storage 에 두고, 파일 I/O 를 한 곳에 모은다.
- [이어하기] 활성 조건은 `storage.load_state() is not None`.

#### 트레이 / 백그라운드 (§4)
- `QSystemTrayIcon` 사용. 트레이 미지원 환경(`QSystemTrayIcon.isSystemTrayAvailable()==False`)에서는 조용히 비활성(예외 금지).
- 최소화 시 트레이로 숨기고, 트레이 더블클릭/메뉴로 복원. 수집은 `QThread` 라 최소화해도 계속 진행.

#### 테스트 격리 (pytest)
- `QApplication` session fixture(Push3 와 동일 패턴).
- `core/run_logger` 는 순수 함수/클래스로 분리해 tmp_path 로 테스트(`monkeypatch` DATA_DIR).
- `ScraperThread` 는 실제 start 하지 않고 신호만 수동 emit 하거나 MagicMock 으로 대체.

### 관련 파일

- `src/ui/main_window.py` — MainWindow (수정 대상)
- `src/core/run_logger.py` — 영속 로그 파일 (신규 생성)
- `src/ui/panels/results_panel.py` — 진행표시/로그 색상 (수정 대상)
- `src/ui/panels/control_panel.py` — [이어하기] 버튼 (수정 대상)
- `src/tests/test_run_logger.py`, `src/tests/test_main_window.py` — 테스트 (신규)

---

## 작업

- [ ] 4.0 메인윈도우/로깅/진행표시 (Push 범위)

    - [ ] 4.1 영속 로그 파일 — `core/run_logger.py`
        **작업 상세:** §8. `RunLogger` 클래스: `__init__` 시 `DATA_DIR/logs` 생성, `run-YYYYMMDD-HHMMSS.log` 파일 오픈. `write(level, step_id, message)` → `[ISO8601] [LEVEL] [step_id] message\n` 기록 + flush. `close()`. 타임스탬프는 `datetime.now()` 사용(테스트는 형식만 검증). 경로는 `storage.DATA_DIR` 동적 참조(모듈 캐시 금지).
        MainWindow 가 스크랩 시작 시 `RunLogger` 생성, `log_signal`/`step_signal`/`skip_signal`/`blocked_signal` 수신 시 파일에도 기록, `done_signal` 시 `close()`.
        **참조:** PRD §8
        - [ ] 4.1.T1 pytest (`tests/test_run_logger.py`, `class TestRunLogger`): tmp DATA_DIR 로 생성 시 logs 디렉토리·파일 생성, `write` 후 파일에 `[LEVEL] [step_id]` 형식 라인 포함, 여러 write 누적, close 후 읽기 가능.
        - [ ] 4.1.T2 `cd src && .venv/bin/pytest tests/test_run_logger.py -v` 실행 및 검증

    - [ ] 4.2 QSystemTrayIcon + 트레이 최소화
        **작업 상세:** §4. MainWindow 에 `_setup_tray()`: 트레이 사용 가능 시 아이콘+컨텍스트 메뉴(표시/종료) 생성. `changeEvent`/최소화 시 `hide()` + 트레이 잔류, 트레이 활성화 시 `showNormal()`. 진행 상태를 `setToolTip`/`showMessage`(알림)로 표시. 미지원 환경 안전 처리.
        **참조:** PRD §4, `src/ui/main_window.py` (`closeEvent`)
        - [ ] 4.2.T1 pytest (`tests/test_main_window.py`, `class TestTray`): qapp 로 MainWindow 생성 시 예외 없음, `_setup_tray` 호출 후 트레이 미지원 환경에서도 안전(속성 None 허용), `isSystemTrayAvailable` False 시 tray 비활성 분기.
        - [ ] 4.2.T2 `cd src && .venv/bin/pytest tests/test_main_window.py::TestTray -v` 실행 및 검증

    - [ ] 4.3 [이어하기] 버튼 + resume 배선
        **작업 상세:** §7. `control_panel.py` 에 **[이어하기]** 버튼(+`resume_requested = pyqtSignal()`). MainWindow 가 시작 시 `storage.load_state()` 존재하면 버튼 활성. 클릭 시 `resume_state` 를 ScraperThread 생성자에 주입해 `_start_scrape(resume=True)`. 신규 스크랩 시작 시 `clear_state()` 후 시작(이어하기 아니면 깨끗이). `_start_scrape` params 구성에 `web/selectors/delays/flow/target/excluded_set` 주입(Push2 생성자 시그니처에 맞춤).
        **참조:** PRD §7, §9, `src/ui/main_window.py` (`_start_scrape`), `src/ui/panels/control_panel.py`
        - [ ] 4.3.T1 pytest (`class TestResume`): tmp DATA_DIR 에 state.json 있을 때 MainWindow 가 이어하기 활성 판단(`storage.load_state() is not None` 로직), 없을 때 비활성. `_start_scrape` 가 resume 플래그에 따라 resume_state 주입 dict 구성(ScraperThread 는 patch/Mock 으로 생성 가로채 인자 검증).
        - [ ] 4.3.T2 `cd src && .venv/bin/pytest tests/test_main_window.py::TestResume -v` 실행 및 검증

    - [ ] 4.4 차단 감지 모달 + skip 신호 배선
        **작업 상세:** §5. `blocked_signal` → `_on_blocked()`: `QMessageBox` 경고(차단 감지·일시정지 안내) + 스크래퍼 일시정지/중단(`self._scraper.stop()` 또는 pause 플래그). `skip_signal` → `_on_skip(username)`: 중복 skip 카운터 증가 + 로그/진행 라벨 갱신.
        **참조:** PRD §5, §6, `src/ui/main_window.py` (`_on_error` 패턴)
        - [ ] 4.4.T1 pytest (`class TestBlockedAndSkip`): `_on_skip` 연속 호출 시 카운터 누적, `_on_blocked` 가 스크래퍼 stop 호출(MagicMock scraper)·예외 없음(QMessageBox 는 patch 또는 modal 회피).
        - [ ] 4.4.T2 `cd src && .venv/bin/pytest tests/test_main_window.py::TestBlockedAndSkip -v` 실행 및 검증

    - [ ] 4.5 진행표시 라벨 + 로그 색상
        **작업 상세:** §8. `results_panel.py` 에 진행 라벨: `태그 t/max_tags · 게시물 p/posts_per_tag · 수집 N · 중복skip M`. `step_signal`/`progress_signal`/`skip_signal` 로 실시간 갱신. 로그 탭은 레벨별 색상(step=`Colors.accent`, info=`Colors.muted2`, warning=`Colors.amber`, error=`Colors.red`) — `append_log` 가 메시지 prefix(`[step]`/`[ERROR]`/`[blocked]`/`[skip]` 등) 보고 색 결정.
        **참조:** PRD §8, `src/ui/panels/results_panel.py`, `src/design/tokens.py`
        - [ ] 4.5.T1 pytest (`class TestProgressLabel`): qapp 로 ResultsPanel 생성, 진행 갱신 메서드 호출 시 라벨 텍스트에 수집/skip 수 반영, 색상 결정 헬퍼가 prefix별 올바른 `Colors.*` 반환(순수 함수로 분리해 테스트).
        - [ ] 4.5.T2 `cd src && .venv/bin/pytest tests/test_main_window.py::TestProgressLabel -v` 실행 및 검증

    - [ ] 4.6 전체 통합 회귀 + 수동 스모크
        **작업 상세:** `cd src && .venv/bin/pytest tests/ -v` 전체 통과. 가능하면 `.venv/bin/python main.py` 로 앱 기동, 트레이 최소화·[이어하기] 비활성/활성·로그 색상 육안 확인(헤드리스면 생략·사유 기록). Push1~4 통합 동작 확인.
        - [ ] 4.6.T1 `cd src && .venv/bin/pytest tests/ -v` 전체 통과 확인
