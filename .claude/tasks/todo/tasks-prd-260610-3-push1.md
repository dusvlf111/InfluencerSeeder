# Tasks: InfluencerSeeder v3 - Push 1 (스토리지 5분리 + state.json + dedup)

> PRD: `.claude/tasks/prd-260610-3.md` (§2, §3, §9 `core/storage.py`)
> Push 범위: `core/storage.py` 를 web/selectors(priority)/delays/flow/target 5분리 + 프로필 중심 results dedup + state.json 재개 상태
> 상태: 🔲 진행 중
> 선행: 없음 (최하단 기반 레이어). Push2~4 가 이 레이어에 의존.

---

### 실행 환경

- **사용 가능 도구:** Read, Write, Edit, Bash, Glob, Grep, Task
- **사용 불가 도구:** Skill, Agent (서브에이전트 중첩 불가)
- **테스트 실행:** `cd src && .venv/bin/pytest tests/test_storage.py -v`
- **전체 테스트:** `cd src && .venv/bin/pytest tests/ -v`
- **이미지 읽기:** Read 도구로 `.png` 직접 열람 가능
- **병렬 작업:** 불가 (순차 실행)
- ⚠️ pytest-qt 미설치 — 이 Push 는 순수 파일 I/O 라 Qt 불필요.

### 참조 이미지

| 이미지 | 용도 | 관련 작업 |
|--------|------|-----------|
| `.claude/tasks/1_돋보기 클릭.png` | Step1 search_icon 셀렉터 기본값 작성 참고 | 1.2 |
| `.claude/tasks/3_테그 클릭.png` | Step3 tag_result 셀렉터 참고 | 1.2 |
| `.claude/tasks/5_게시물에서 프로필 클릭.png` | Step5 profile_link 셀렉터 참고 | 1.2 |
| `.claude/tasks/6_프로필 이미지에서 정보 저장.png` | results.csv 컬럼(팔로워/팔로우/게시물/소개/웹사이트) 매핑 | 1.2, 1.6 |

### 참조 문서

작업 시작 전 반드시 아래를 `Read`로 읽을 것:

| 문서 | 용도 |
|------|------|
| `.claude/tasks/prd-260610-3.md` | §2 설정 5그룹 CSV 스키마, §3 데이터 스키마, §9 storage 시그니처 |
| `src/core/storage.py` | 기존 CSV 로드/저장 패턴 (수정 대상) — `_coerce`, `utf-8-sig`, defaults 기록 |
| `src/tests/test_storage.py` | 기존 테스트 패턴 (autouse `tmp_data_dir` fixture) — **주의: 현재 storage.py 와 일부 불일치, 새 함수에 맞춰 갱신** |
| `src/core/scraper.py` | storage 를 소비하는 쪽 (Push2 에서 수정) — 시그니처 호환 확인용 |

### 적용 규칙 (프로젝트 컨벤션)

#### 스토리지 (파일 I/O 격리)
- 파일 I/O 는 `core/storage.py` 에만 둔다. 경로는 모두 `DATA_DIR` 기준.
- `DATA_DIR = Path(__file__).parent / "data"` (현재 = `src/core/data`). **이 정의를 바꾸지 말 것** — 테스트가 `monkeypatch.setattr(storage, "DATA_DIR", tmp_path)` 로 덮어쓴다.
- CSV 입출력은 `encoding="utf-8-sig"`, `newline=""`, `csv.DictReader`/`csv.DictWriter` 사용 (기존 패턴 그대로).
- **파일이 없으면** 첫 load 시 기본값을 기록(save)한 뒤 반환한다 (기존 `load_settings`/`load_selectors` 동작 유지).
- 손상된 파일은 `try/except` 로 감싸 기본값/빈값 반환 (절대 예외 전파 금지).
- 문자열→숫자 변환은 기존 `_coerce()` 재사용.

#### 마이그레이션
- v2 의 `settings.csv` 단일 파일을 `web.csv`/`delays.csv`/`flow.csv`/`target.csv` 로 분리한다.
- 기존 `load_settings`/`save_settings` 는 **삭제하지 말고 유지** (Push2/3 가 아직 참조). 단, 신규 함수로 점진 대체 가능하도록 추가만 한다.
- 기존 `load_excluded`/`save_excluded`, `load_results`/`append_result`/`export_results` 는 유지하되 1.6 에서 스키마 확장.

#### 테스트 격리 (pytest)
- `storage` 테스트: autouse fixture 로 `monkeypatch.setattr(storage, "DATA_DIR", tmp_path)`.
- 실제 네트워크/브라우저 호출 절대 금지.
- 클래스 단위로 묶기 (`class TestWeb`, `class TestSelectors`, ...). 정상→엣지(빈/None/손상)→예외 순.

### 관련 파일

- `src/core/storage.py` — CSV 스토리지 (수정 대상)
- `src/tests/test_storage.py` — 테스트 (추가/갱신 대상)

---

## 작업

- [ ] 1.0 storage.py 5분리 + dedup + state (Push 범위)

    - [x] 1.1 web.csv — `load_web()` / `save_web(dict)`
        **작업 상세:** §2.1 스키마(key,value)로 `_WEB_DEFAULTS` 정의:
        `browser=chrome, headless=false, window_width=1280, window_height=900, randomize_window=true, randomize_user_agent=true, user_data_dir=(빈값), locale=ko-KR, implicit_wait=5, page_load_timeout=30`.
        `load_web()` 는 `load_settings` 와 동일 패턴(파일 없으면 save 후 반환, `_coerce` 적용, 손상 시 defaults). `save_web(dict)` 는 key,value 헤더로 기록. bool 값은 `"true"/"false"` 문자열로 저장하되 load 시 `_coerce` 가 문자열로 남기므로, 소비측에서 `str(v).lower()=="true"` 로 해석 가능하도록 `web_defaults()` 헬퍼도 제공.
        **참조:** PRD §2.1, `src/core/storage.py` (load_settings 패턴)
        - [x] 1.1.T1 pytest 테스트 작성 (`tests/test_storage.py` 에 `class TestWeb` 추가): 파일 없을 때 defaults 반환·파일 생성, round-trip, 손상 파일 시 defaults, 누락 키 기본값 머지.
        - [x] 1.1.T2 `cd src && .venv/bin/pytest tests/test_storage.py::TestWeb -v` 실행 및 검증

    - [x] 1.2 selectors.csv 확장 — priority + fallback 체인
        **작업 상세:** §2.2 스키마로 `_SELECTOR_FIELDNAMES = ["step_id","step_name","priority","selector_type","selector_value"]` 확장.
        `_SELECTOR_DEFAULTS` 를 PRD §2.2 표(step 당 여러 후보 + priority) 기준으로 재작성 — 최소 step_id: `search_icon, search_input, tag_result, post_link, profile_link, username_text, followers_count, following_count, posts_count, bio_text, website_link`.
        `load_selectors() -> list[dict]` 는 **`step_id` 별로 `priority` 오름차순 정렬**해 반환 (priority 결측 시 `9999`). `priority` 는 `_coerce` 로 int 화. `save_selectors(rows)` 는 새 필드 포함.
        하위호환: 기존 행에 `priority` 없으면 기본 `1` 로 채운다. `coord` 타입(`selector_value="x,y"`)도 허용(검증은 Push2).
        **참조:** PRD §2.2, 이미지 `1_돋보기 클릭.png`/`3_테그 클릭.png`/`5_게시물에서 프로필 클릭.png`/`6_프로필 이미지에서 정보 저장.png`, `src/core/storage.py` (selector 패턴), `src/core/scraper.py` `_get_by`
        - [x] 1.2.T1 pytest 테스트 (`class TestSelectors`): defaults 반환·파일 생성, priority 오름차순 정렬 검증, round-trip(새 필드), priority 결측 시 보정, 손상 파일 시 defaults.
        - [x] 1.2.T2 `cd src && .venv/bin/pytest tests/test_storage.py::TestSelectors -v` 실행 및 검증

    - [x] 1.3 delays.csv — `load_delays()` / `save_delays(dict)`
        **작업 상세:** §2.3 스키마(step_id,delay_min,delay_max). `_DELAY_DEFAULTS` 에 `step1~step6, back, scroll, typing_char` 의 (min,max) 정의(PRD 값 그대로).
        `load_delays() -> dict[str, tuple[float,float]]` (예: `{"step1": (1.0, 2.5), ...}`). 파일 없으면 defaults 기록 후 반환. `save_delays(dict)` 는 step_id,delay_min,delay_max 헤더로 기록. 손상/누락 시 해당 키는 defaults 로 머지.
        **참조:** PRD §2.3
        - [x] 1.3.T1 pytest 테스트 (`class TestDelays`): defaults 반환·생성, round-trip, tuple 형태 검증, 누락 키 머지, 손상 파일 시 defaults.
        - [x] 1.3.T2 `cd src && .venv/bin/pytest tests/test_storage.py::TestDelays -v` 실행 및 검증

    - [x] 1.4 flow.csv — `load_flow()` / `save_flow(dict)`
        **작업 상세:** §2.4 스키마(key,value). `_FLOW_DEFAULTS`: `max_tags=3, tag_start_index=0, posts_per_tag=5, scroll_max_attempts=15, skip_visited_profile=true, stop_on_consecutive_miss=10`. load/save 는 1.1 web 과 동일 패턴, `_coerce` 적용.
        **참조:** PRD §2.4
        - [x] 1.4.T1 pytest 테스트 (`class TestFlow`): defaults 반환·생성, round-trip, 누락 키 머지, 손상 파일 시 defaults.
        - [x] 1.4.T2 `cd src && .venv/bin/pytest tests/test_storage.py::TestFlow -v` 실행 및 검증

    - [ ] 1.5 target.csv — `load_target()` / `save_target(dict)`
        **작업 상세:** §2.5 스키마(key,value). `_TARGET_DEFAULTS`: `min_followers=0, max_followers=0, min_following=0, max_following=0, min_posts=0, keyword=(빈값), mode=hashtag`. load/save 동일 패턴.
        **참조:** PRD §2.5
        - [ ] 1.5.T1 pytest 테스트 (`class TestTarget`): defaults 반환·생성, round-trip, 누락 키 머지, 손상 파일 시 defaults.
        - [ ] 1.5.T2 `cd src && .venv/bin/pytest tests/test_storage.py::TestTarget -v` 실행 및 검증

    - [ ] 1.6 results.csv 프로필 스키마 + dedup append + `seen_usernames()`
        **작업 상세:** §3.1 로 `_RESULTS_FIELDNAMES` 교체:
        `["username","full_name","followers","following","posts_count","bio","website","is_private","profile_url","source_tag","source_post_url","collected_at"]`.
        `append_result(info) -> bool`: 저장 전 `username` 을 **소문자 정규화**, `results.csv` + `excluded.csv` 의 username 집합과 대조해 **중복이면 append 안 하고 False 반환**, 신규면 append 후 True. (기존 호출부 호환 위해 반환값 추가는 안전.)
        `seen_usernames() -> set[str]`: `load_results()` username ∪ `load_excluded()` 를 **소문자 정규화 set** 으로 반환.
        `load_results()` 는 유지(새 필드 자동 반영). 하위호환: 옛 컬럼(`post_url`) 데이터가 있어도 깨지지 않게 `DictReader` 그대로.
        **참조:** PRD §3.1, 이미지 `6_프로필 이미지에서 정보 저장.png`, `src/core/storage.py` (append_result)
        - [ ] 1.6.T1 pytest 테스트 (`class TestResultsDedup`): 신규 append True·파일 기록, 동일 username(대소문자 차이) 재append False, excluded 에 있는 username append False, `seen_usernames()` 가 results+excluded 합집합 소문자 반환.
        - [ ] 1.6.T2 `cd src && .venv/bin/pytest tests/test_storage.py::TestResultsDedup -v` 실행 및 검증

    - [ ] 1.7 state.json — `load_state()` / `save_state(dict)` / `clear_state()`
        **작업 상세:** §3.3 스키마. `import json`. `STATE_PATH = DATA_DIR / "state.json"` 은 함수 내에서 `DATA_DIR` 참조(테스트 monkeypatch 대응 — 모듈 상수로 캐시하지 말 것).
        `save_state(dict)`: `_ensure_data_dir()` 후 json dump(`ensure_ascii=False, indent=2`). `load_state() -> dict | None`: 없거나 손상 시 `None`. `clear_state()`: 파일 있으면 삭제(`Path.unlink(missing_ok=True)`).
        **참조:** PRD §3.3, §7 Resume
        - [ ] 1.7.T1 pytest 테스트 (`class TestState`): 없을 때 load None, save→load round-trip, clear 후 load None, 손상 json load None, seen_usernames 리스트 보존.
        - [ ] 1.7.T2 `cd src && .venv/bin/pytest tests/test_storage.py::TestState -v` 실행 및 검증

    - [ ] 1.8 전체 회귀 검증
        **작업 상세:** `cd src && .venv/bin/pytest tests/ -v` 실행. 기존 `test_scraper_utils.py` 가 깨지지 않는지 확인(이 Push 는 scraper 미수정). 기존 `test_storage.py` 의 stale 테스트(`max_scroll`, `sel_tab_recent` 등 현행 코드에 없는 키 참조)가 있으면 **현행 동작에 맞게 수정하거나 제거**하고 사유를 커밋 메시지에 기록.
        - [ ] 1.8.T1 `cd src && .venv/bin/pytest tests/ -v` 전체 통과 확인
