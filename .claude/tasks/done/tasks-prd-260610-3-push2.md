# Tasks: InfluencerSeeder v3 - Push 2 (스크래퍼 stealth + selector fallback + resume + flow 최적화)

> PRD: `.claude/tasks/prd-260610-3.md` (§4 백그라운드, §5 stealth, §6 flow 최적화, §9 `core/scraper.py`)
> Push 범위: `core/scraper.py` ScraperThread — priority 셀렉터 폴백, stealth 핑거프린트, 사람같은 타이핑, 조기 dedup skip, state 재개, 차단 감지, 신규 신호
> 상태: 🔲 진행 중
> 선행: **Push 1 완료 필수** (storage 신규 함수 `load_web/load_selectors(priority)/load_delays/load_flow/load_target/load_state/save_state/seen_usernames` 사용).

---

### 실행 환경

- **사용 가능 도구:** Read, Write, Edit, Bash, Glob, Grep, Task
- **사용 불가 도구:** Skill, Agent
- **테스트 실행:** `cd src && .venv/bin/pytest tests/test_scraper_utils.py -v`
- **전체 테스트:** `cd src && .venv/bin/pytest tests/ -v`
- **이미지 읽기:** Read 도구로 `.png` 직접 열람 가능
- **병렬 작업:** 불가
- ⚠️ 실제 브라우저/네트워크 호출 금지 — 모든 selenium 호출은 `MagicMock()` 으로 테스트.

### 참조 이미지

| 이미지 | 용도 | 관련 작업 |
|--------|------|-----------|
| `.claude/tasks/1_돋보기 클릭.png` | Step1 search_icon 위치 (selector 폴백 대상) | 2.1 |
| `.claude/tasks/2_검색 클릭.png` | Step2 검색 입력 — 사람같은 타이핑 대상 | 2.3 |
| `.claude/tasks/3_테그 클릭.png` | Step3 태그 결과 | 2.1 |
| `.claude/tasks/4_이미지 클릭.png` | Step4 게시물 그리드 | 2.4 |
| `.claude/tasks/5_게시물에서 프로필 클릭.png` | Step5 프로필 진입 전 username 추출(조기 skip 게이트) | 2.4 |
| `.claude/tasks/6_프로필 이미지에서 정보 저장.png` | Step6 프로필 데이터 추출 | 2.5 |

### 참조 문서

작업 시작 전 반드시 `Read`로 읽을 것:

| 문서 | 용도 |
|------|------|
| `.claude/tasks/prd-260610-3.md` | §4 headless, §5 stealth 풀/토글, §6 조기 dedup 게이트, §9 scraper 메서드 시그니처 |
| `src/core/scraper.py` | ScraperThread 구조·신호·step 메서드 (수정 대상) |
| `src/core/storage.py` | Push1 신규 함수 시그니처 (이 Push 가 호출) — `load_web/load_selectors/load_delays/load_flow/load_target/load_state/save_state/clear_state/seen_usernames/append_result(dedup)` |
| `src/tests/test_scraper_utils.py` | 기존 테스트 패턴 — `ScraperThread.__new__` 로 `__init__` 우회, `MagicMock` 드라이버 |

### 적용 규칙 (프로젝트 컨벤션)

#### 신호/슬롯 (UI 안전성)
- `ScraperThread` 는 `QThread` 서브클래스. **UI 위젯을 직접 조작하지 않는다.** 오직 `pyqtSignal` emit 으로만 통신.
- 기존 신호: `log_signal(str)`, `progress_signal(int,int)`, `result_signal(dict)`, `done_signal()`, `error_signal(str)`, `waiting_login_signal()`, `step_signal(str)`.
- 신규 신호 추가: `skip_signal(str)` (중복 skip 된 username), `blocked_signal()` (차단 감지). 기존 신호 시그니처는 **변경 금지**(소비측 main_window 호환).
- `run()` 내부 예외는 `error_signal` emit 후 `finally` 에서 `driver.quit()` + `done_signal` (기존 패턴 유지).

#### 스토리지 경유
- 파일 I/O 는 직접 하지 않고 `core.storage` 함수 호출. state 저장은 `storage.save_state()`.
- dedup 판정 set 은 `storage.seen_usernames()` + 생성자 주입 `excluded_set` 합집합.

#### 봇 탐지 회피 (§5)
- 모든 step 사이 딜레이는 `delays.csv`(`storage.load_delays()`) 범위 내 `random.uniform`.
- 타이핑은 글자별 `typing_char` 딜레이.
- stealth: UA 풀 랜덤, 창크기 프리셋 랜덤, `--disable-blink-features=AutomationControlled` + `navigator.webdriver` 제거(기존 init_driver 에 일부 존재 — 확장).
- 차단(로그인/챌린지 리다이렉트) 감지 시 즉시 `blocked_signal` emit + 루프 일시정지/종료.

#### 테스트 격리 (pytest)
- selenium 드라이버·요소는 전부 `MagicMock()`. `ScraperThread.__new__(ScraperThread)` 로 인스턴스 생성 후 필요한 속성만 수동 세팅(기존 `_make_thread` 패턴).
- `time.sleep` 은 `monkeypatch` 또는 `patch("core.scraper.time.sleep")` 로 무력화.
- 실제 `random` 분기 검증은 `patch("core.scraper.random.uniform", return_value=...)`.

### 관련 파일

- `src/core/scraper.py` — ScraperThread (수정 대상)
- `src/core/storage.py` — Push1 함수 호출 (수정 안 함, 호환 확인)
- `src/tests/test_scraper_utils.py` — 테스트 (추가 대상)

---

## 작업

- [x] 2.0 ScraperThread stealth/resume/flow (Push 범위)

    - [x] 2.1 `_resolve_selector(step_id)` — priority 폴백 체인
        **작업 상세:** §9. 생성자에서 `storage.load_selectors()`(priority 정렬됨)를 `step_id -> [row,...]` 리스트로 그룹화해 보관(`self._selector_chains`).
        `_resolve_selector(self, driver, step_id) -> (element | None)`: 해당 step_id 후보를 priority 순회하며 `selector_type` 에 따라 `By.XPATH`/`By.CSS_SELECTOR` 로 `find_elements`, **처음 매칭(len>0)되는 첫 요소 반환**. `coord` 타입이면 `selector_value="x,y"` 파싱해 좌표 폴백 정보 반환(클릭은 호출측). 모두 실패 시 `None` + `log_signal` 에러. 사용된 priority/매칭 개수를 `_log`.
        기존 `_get_by` 는 유지하되 step 메서드들이 `_resolve_selector` 를 쓰도록 점진 전환(2.1 에서는 헬퍼 추가 + 1곳 이상 적용).
        **참조:** PRD §2.2, §9, 이미지 `1_돋보기 클릭.png`
        - [x] 2.1.T1 pytest (`class TestResolveSelector`): MagicMock driver 로 priority1 매칭 시 priority1 반환, priority1 빈 결과→priority2 폴백, 전부 실패→None, coord 타입 파싱.
        - [x] 2.1.T2 `cd src && .venv/bin/pytest tests/test_scraper_utils.py::TestResolveSelector -v` 실행 및 검증

    - [x] 2.2 `_apply_stealth(driver)` + UA/창크기 랜덤 + headless
        **작업 상세:** §5. 모듈 상수 `_UA_POOL = [...]`(데스크톱 Chrome UA 4~6개), `_WINDOW_PRESETS = [(1280,900),(1440,900),(1366,768),(1536,864)]`.
        `init_driver(web: dict | None = None)` 확장: `web.csv` 토글 반영 — `headless=true` 면 `--headless=new`; `randomize_user_agent=true` 면 `_UA_POOL` 에서 랜덤 UA `--user-agent=`; `randomize_window=true` 면 프리셋 랜덤 `--window-size=`, 아니면 `window_width/height`; `user_data_dir` 채워지면 `--user-data-dir=`; `--disable-blink-features=AutomationControlled` 유지.
        `_apply_stealth(driver)`: `navigator.webdriver` 제거 스크립트 주입(기존 execute_script 유지/확장).
        ⚠️ `random` 사용처는 테스트에서 patch 가능하도록 `core.scraper.random` 통해 호출.
        **참조:** PRD §5, §4 headless, `src/core/scraper.py` `init_driver`
        - [x] 2.2.T3 [window_width=0 폴백 오류] `0 or 1280` 단락평가로 0이 1280으로 치환되던 문제 수정 (빈문자만 기본값 적용)
        - [x] 2.2.T1 pytest (`class TestStealth`): `randomize_user_agent` 토글 시 UA 인자 추가 여부, `randomize_window` True/False 시 window-size 분기, `headless=true` 시 `--headless=new` 추가. Options 객체는 실제 selenium Options 또는 MagicMock 으로 add_argument 호출 인자 검증(webdriver.Chrome 은 patch).
        - [x] 2.2.T2 `cd src && .venv/bin/pytest tests/test_scraper_utils.py::TestStealth -v` 실행 및 검증

    - [x] 2.3 `_human_type(el, text)` — 글자별 딜레이 타이핑
        **작업 상세:** §5. `typing_char` 딜레이(`self._delays["typing_char"]` = (min,max))를 글자마다 `random.uniform` 후 `el.send_keys(ch)` + `time.sleep`. 빈 문자열 안전 처리. 호출 횟수 = `len(text)`.
        Step2 `_step2_type_search` 가 `inp.send_keys` 대신 `_human_type(inp, f"#{keyword}")` 쓰도록 교체.
        **참조:** PRD §5, 이미지 `2_검색 클릭.png`
        - [x] 2.3.T1 pytest (`class TestHumanType`): MagicMock el 로 `send_keys` 호출 횟수 == len(text), `time.sleep` patch 호출됨, 빈 문자열 시 호출 0회.
        - [x] 2.3.T2 `cd src && .venv/bin/pytest tests/test_scraper_utils.py::TestHumanType -v` 실행 및 검증

    - [x] 2.4 `_should_skip(username)` — 조기 dedup 게이트 (§6)
        **작업 상세:** §6. `self._seen` set(= `storage.seen_usernames()` ∪ 정규화된 `excluded_set`, 생성자에서 구성) 기준.
        `_should_skip(self, username) -> bool`: `username.lstrip("@").lower()` 가 `self._seen` 에 있으면 True. True 면 `skip_signal.emit(username)` + `_log("[skip] 중복 건너뜀")`. 필터 미통과 username 도 `self._seen.add()` 로 재방문 방지(저장은 호출측).
        run() 플로우에 게이트 삽입: Step4 게시물 진입 후 가능한 한 **프로필 진입(Step5) 전** 헤더에서 username 추출해 `_should_skip` → True 면 Step5/6 생략하고 다음 게시물.
        **참조:** PRD §6, 이미지 `5_게시물에서 프로필 클릭.png`
        - [x] 2.4.T1 pytest (`class TestShouldSkip`): seen 에 있는 username True + skip_signal emit, 없는 username False, 대소문자/@ 정규화, 필터 탈락 username add 후 재호출 True.
        - [x] 2.4.T2 `cd src && .venv/bin/pytest tests/test_scraper_utils.py::TestShouldSkip -v` 실행 및 검증

    - [x] 2.5 생성자 재편 + state 재개 + step 완료마다 save_state
        **작업 상세:** §9. 생성자 시그니처를 PRD 기준으로 확장: `web, selectors, delays, flow, target, excluded_set, resume_state=None` 주입(기존 호출부 호환 위해 **키워드 기본값** 제공, 누락 시 `storage.load_*()` 로 자체 로드).
        `flow` 에서 `max_tags/posts_per_tag/scroll_max_attempts/tag_start_index/stop_on_consecutive_miss/skip_visited_profile` 읽기. `target` 에서 필터(min/max followers·following·posts) 읽기.
        `resume_state` 있으면 `tag_index=state["tag_index"]`, `post_index=state["post_index"]` 부터 시작, `seen` 에 `state["seen_usernames"]` 선로딩.
        매 step 완료 후 `storage.save_state({...})` 호출. 수집 완료/종료 시 정책에 따라 `clear_state()` (정상 완료 시).
        `append_result` 가 dedup False 반환하면 저장 skip 처리(중복 카운트 안 함).
        **참조:** PRD §3.3, §7, §9
        - [x] 2.5.T1 pytest (`class TestResumeAndState`): 생성자에 web/delays/flow/target/excluded 주입 시 속성 매핑 검증, resume_state 주입 시 tag/post index·seen 선로딩, `save_state` 가 `storage.save_state` 를 올바른 dict 로 호출(patch).
        - [x] 2.5.T2 `cd src && .venv/bin/pytest tests/test_scraper_utils.py::TestResumeAndState -v` 실행 및 검증

    - [x] 2.6 차단 감지 → `blocked_signal` + 일시정지
        **작업 상세:** §5 한계. `_is_blocked(driver) -> bool`: `driver.current_url` 가 로그인/챌린지 경로(`/accounts/login`, `/challenge`, `/accounts/suspended` 등) 포함이면 True. run() 의 각 네비게이션 후 검사 → True 면 `blocked_signal.emit()` + `_log("[blocked] 차단 감지 - 일시정지")` + 루프 중단(`self._stop` 또는 대기). 로그인 대기와 구분.
        **참조:** PRD §5
        - [x] 2.6.T1 pytest (`class TestBlockedDetection`): MagicMock driver.current_url 가 challenge/login URL 일 때 `_is_blocked` True, 정상 프로필 URL 일 때 False.
        - [x] 2.6.T2 `cd src && .venv/bin/pytest tests/test_scraper_utils.py::TestBlockedDetection -v` 실행 및 검증

    - [x] 2.7 전체 회귀 검증
        **작업 상세:** `cd src && .venv/bin/pytest tests/ -v`. 기존 `TestParseFollowers`/`TestScraperThreadIsValidUsername`/`TestScraperThreadPassesFollowerFilter` 가 깨지지 않는지 확인(기존 메서드 시그니처 유지). 깨졌으면 호환되도록 수정.
        - [x] 2.7.T1 `cd src && .venv/bin/pytest tests/ -v` 전체 통과 확인 (124 passed)
