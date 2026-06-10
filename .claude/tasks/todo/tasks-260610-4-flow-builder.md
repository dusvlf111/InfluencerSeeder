# Tasks: 260610-4 — 동적 플로우 빌더 + 버튼매핑 가이드(이미지/설명) + 설정 CSV 폴더 공유

> 목적: 6스텝 하드코딩 플로우를 **flow_steps.csv 기반 ConfigurableFlow** 로 전환하고,
> 설정 UI에 **스텝 이미지+XPath 복사 가이드 / 플로우 빌더(스텝 추가·삭제·순서·액션) / 셀렉터 후보 편집 / 설정 CSV 폴더 단위 가져오기·내보내기** 를 추가한다.
> 상태: 🔲 대기. 선행: refactor-1(flows 추상화) 완료. 후행: 없음.

---

## Context (왜)

PRD v3 §2.2/§2.4 는 버튼매핑을 **고정 6스텝 + 셀렉터 후보 편집**으로 설계했다. 사용자는 여기서 더 나아가:
1. 설정 화면 버튼매핑 탭에 **스텝별 스크린샷 + "웹에서 XPath 복사하는 법" 설명**을 넣고,
2. **사용자가 플로우 스텝을 직접 추가/생성·순서변경**하고 각 스텝의 **액션(클릭/타이핑/태그선택/링크수집/프로필이동/정보추출/뒤로가기/스크롤/대기)** 을 지정하며,
3. 이 설정을 **CSV로 공유** — *폴더로 내보내면 각 CSV를 파일명대로 넣고, 가져올 때 폴더를 선택하면 파일명에 맞춰 알아서 읽어들임* (사용자 확정).

현재 `core/flows/`(Step/Flow + registry, refactor-1 완료)가 이미 있으나 `HashtagFlow.run()` 은 6스텝을 **코드로 하드코딩**해 조립한다. 본 작업은 이 조립을 **데이터(flow_steps.csv) 기반 인터프리터**로 바꿔 사용자가 플로우를 편집 가능하게 만든다.

스크린샷 원본: `.claude/tasks/{1_돋보기 클릭, 2_검색 클릭, 3_테그 클릭, 4_이미지 클릭, 5_게시물에서 프로필 클릭, 6_프로필 이미지에서 정보 저장}.png`.

---

### 실행 환경
- **사용 가능 도구:** Read, Write, Edit, Bash, Glob, Grep
- **테스트:** `cd src && .venv/bin/pytest tests/ -v` (매 커밋마다 **전체** 통과 유지)
- **앱 실행 확인:** `cd src && .venv/bin/python main.py`
- **병렬 작업:** 불가 (P0→P5 순차)

### 참조 문서 (작업 전 Read)
| 문서 | 용도 |
|------|------|
| `src/CLAUDE.md` | 신호/슬롯·스토리지 격리·토큰·테스트 격리 규칙 |
| `.claude/tasks/prd-260610-3.md` §2.2/§2.4 | 셀렉터 fallback 체인 / flow 노브 원안 |
| `src/core/flows/{base,context,__init__,steps,hashtag}.py` | Step/Flow/Outcome/registry/재사용 Step |
| `src/core/storage.py` | CSV 헬퍼(`_load_kv/_save_kv`, selectors load/save, DATA_DIR 규칙) |
| `src/ui/settings_view.py` | 현행 QTabWidget 설정 화면(버튼매핑=Selectors 탭) |
| `src/build.spec` | PyInstaller datas (이미지 번들링) |

### ⚠️ 깨면 안 되는 계약
- `core/scraper.py` 는 `.py` 모듈 유지, `_passes_follower_filter`/역량 메서드/생성자 시그니처 불변(refactor-1 계약).
- 기존 신호 시그니처 불변 — 새 기능은 신호 **추가**로만. Step/Flow 는 UI 직접 조작 금지(`ctx.thread.<signal>.emit` 만).
- 파일 I/O 는 `core/storage.py` 에만. 경로는 함수 내 `DATA_DIR` 참조(모듈 상수 캐시 금지) — 테스트가 monkeypatch.
- **기본 flow_steps.csv 는 현행 6스텝과 동작 동일** — 전환 후에도 기존 flow 테스트(`test_flows.py`)·로그 prefix(`[1]`~`[6]`/`[skip]`/`[OK]`/`[grid]`)·신호 순서가 그대로여야 함.

---

## 설계 요약

### 새 파일 `data/flow_steps.csv` (순서 있는 액션 시퀀스)
```
order,phase,step_name,action,selector_ref,param,enabled
1,per_tag,돋보기 클릭,click,search_icon,,true
2,per_tag,검색 입력,type,search_input,#{keyword},true
3,per_tag,태그 클릭,click_index,tag_result,{tag_index},true
4,per_tag,게시물 URL 수집,collect_open,post_link,{posts_per_tag},true
5,per_post,중복 조기판정,peek_gate,profile_link,,true
6,per_post,프로필 이동,navigate_profile,profile_link,,true
7,per_post,정보 추출,extract,profile_fields,,true
8,per_post,필터,filter,,,true
9,per_post,저장,save,,,true
10,per_post,뒤로가기,go_back,,,true
```
- `phase`: `pre_loop`(런당 1회) | `per_tag`(태그마다) | `per_post`(게시물마다). `collect_open` 이 per_tag→per_post 루프 경계를 만든다.
- `action`: 고정 **액션 어휘**(아래). `selector_ref` = `selectors.csv` 의 `step_id`(후보 체인). `param` = 템플릿(`#{keyword}`,`{tag_index}`,`{posts_per_tag}`,딜레이 키 등).
- `enabled=false` 면 그 스텝 건너뜀 → 사용자가 토글/추가/삭제/순서변경으로 플로우 구성.

### 액션 어휘 → 기존 Step 매핑 (재사용)
| action | 핸들러 | 비고 |
|--------|--------|------|
| `open_home` | OpenHomeIfNeeded(신규, 기존 인라인 로직 이전) | |
| `click` | ClickSearchIcon 일반화 → `ClickStep(ref)` | 좌표 폴백 유지 |
| `type` | TypeSearch 일반화 → `TypeStep(ref, param)` | `_human_type` |
| `click_index` | ClickTagSuggestion 일반화 → `ClickIndexStep(ref, idx)` | |
| `collect_open` | CollectPostUrls + 내부 post 루프 구동 | |
| `peek_gate` | PeekUsernameGate | SKIP_POST |
| `navigate_profile` | NavigateToProfile | |
| `extract` | ExtractProfile | |
| `filter` | ApplyFilters | SKIP_POST + seen |
| `save` | SaveResult | |
| `go_back` | GoBackStep(신규) | `driver.get(tag_grid_url)`(기본) 또는 `driver.back()` |
| `scroll` | ScrollStep(신규) | 랜덤 스크롤 |
| `wait` | `ctx.thread._random_delay(param)` | |

→ `core/flows/registry_actions.py`(또는 steps.py 확장): `ACTIONS: dict[str, Callable[..., Step]]`. `ConfigurableFlow.run()` 이 flow_steps 를 phase별로 해석해 실행(Outcome 분기·resume 인덱스·차단 감지·딜레이는 현행 HashtagFlow 로직 보존).

### CSV 폴더 공유 (사용자 확정 방식)
- **내보내기**: `QFileDialog.getExistingDirectory` 로 폴더 선택 → 알려진 설정 CSV 각각을 **그 폴더 안에 표준 파일명 그대로** 저장(`web.csv`, `delays.csv`, `selectors.csv`, `flow.csv`, `flow_steps.csv`, `target.csv`, `excluded.csv`). (옵션: 어떤 항목 내보낼지 체크 선택)
- **가져오기**: 폴더 선택 → 그 폴더 안에 **존재하는 표준 파일명만** 자동 인식해 각각 읽어 `DATA_DIR` 로 반영(헤더 검증 후 교체). 통합 단일 파일 형식 **없음**.

---

## 작업

- [x] **P0 — 이미지 에셋 번들링**
    - [x] P0.1 `.claude/tasks/{1..6}_*.png` → `src/assets/guide/step{1..6}.png` 복사(영문 파일명). 신규 `src/core/assets.py` 에 `guide_image_path(step_no) -> Path` 헬퍼: 개발 시 `assets/guide/`, PyInstaller 시 `sys._MEIPASS/assets/guide/` 둘 다 처리.
    - [x] P0.2 `build.spec` `datas` 에 `(str(BASE/"assets"), "assets")` 추가.
    - [x] P0.T `tests/test_assets.py` 4개 통과 + 경로 스모크. 커밋: `feat(assets): bundle step guide screenshots`

- [x] **P1 — storage: flow_steps + 액션상수 + 폴더 가져오기/내보내기**
    - [x] P1.1 `storage_defaults._FLOW_STEPS_DEFAULTS/_FLOW_STEPS_FIELDNAMES` + 신규 `core/storage_flowsteps.py`(`flow_steps_defaults/load_flow_steps/save_flow_steps`, 결측 시 기본값 기록, order 정렬, enabled bool 정규화). facade 재export.
    - [x] P1.2 `FLOW_ACTIONS`(storage_defaults, facade 재export). 미지원 action load 시 logging 후 제외(예외 전파 없음).
    - [x] P1.3 신규 `core/storage_share.py`: `CONFIG_FILES`, `export_config_to_dir(dest,names=None)`(write-on-load 파일 materialize 후 copy2, excluded 는 존재 시만), `import_config_from_dir(src)->list[str]`(존재하는 표준 파일명만 CSV 검증 후 복사, 반영 목록 반환).
    - [x] P1.T `tests/test_storage_flowsteps.py` 13개(round-trip/순서/enabled/미지원 action drop/export→import 왕복/부분 폴더/비CSV skip). 전체 **153 passed**. 커밋: `feat(storage): flow_steps + folder-based config import/export`

- [x] **P2 — flows: 액션 레지스트리 + ConfigurableFlow**
    - [x] P2.1 기존 Step 일반화: `ClickStep/TypeStep/ClickIndexStep` 이 `selector_ref`/`param` 을 받게(기존 고정 step_id 기본값 유지로 하위호환). 신규 `OpenHomeIfNeeded/GoBackStep/ScrollStep`.
    - [x] P2.2 `ACTIONS` 레지스트리(action 문자열→Step 팩토리). `ConfigurableFlow(Flow)`: `mode="hashtag"`(default 교체), `run(ctx)` 가 `load_flow_steps()` 를 phase별로 해석(per_tag 루프 안에서 `collect_open` 이후 per_post 루프 진입, Outcome 분기·resume·차단·`_save_state`·딜레이 보존). flow_steps 비었거나 손상 시 **현행 하드코딩 HashtagFlow 로 폴백**.
    - [x] P2.3 `register("hashtag", ConfigurableFlow)`; 기존 `HashtagFlow` 는 `register("hashtag_legacy", ...)` 로 보존(폴백/회귀 비교용).
    - [x] P2.T `tests/test_flows.py`: 기본 flow_steps 로 `ConfigurableFlow` 가 HashtagFlow 와 **동일 신호·로그·append_result 호출**(Mock driver), enabled=false 스텝 스킵, go_back 동작, 미지원 action 무시. **전체 pytest 통과(222 passed)**. 커밋: `feat(flows): data-driven ConfigurableFlow from flow_steps.csv`

- [ ] **P3 — settings UI: 버튼매핑 탭 재설계(이미지+가이드+셀렉터)**
    - [ ] P3.1 "Selectors" 탭 → **"버튼매핑"** 탭: step_id 그룹별 카드(`QScrollArea`) — 상단 `QLabel`(pixmap = `guide_image_path`), 그 아래 **가이드 텍스트**("브라우저에서 요소 우클릭 → 검사(Inspect) → 강조된 요소 우클릭 → Copy → **Copy XPath**(또는 Copy selector) → 아래 값 칸에 붙여넣기. type 은 xpath/css/coord."), 그 아래 해당 step 의 **셀렉터 후보 표**(priority/type/value 행 추가·삭제·정렬).
    - [ ] P3.2 디자인 토큰만 사용(`design/tokens.py`), objectName 부여 후 `design/stylesheet.py` 규칙. hex 직접 작성 금지.
    - [ ] P3.T 앱 실행 — 카드/이미지/가이드/표 렌더 + 저장 왕복 확인. 커밋: `feat(settings): button-mapping cards with screenshots + XPath guide`

- [ ] **P4 — settings UI: 플로우 빌더**
    - [ ] P4.1 신규 **"플로우"** 탭: flow_steps 표(order/phase/step_name/action(드롭다운=`FLOW_ACTIONS`)/selector_ref(드롭다운=selectors step_id)/param/enabled(체크박스)). **행 추가/삭제/위로/아래로**(order 재계산), [기본 플로우로 초기화].
    - [ ] P4.2 `_collect_flow_steps()/_populate` 연동 + `save_flow_steps` 를 `_save_all` 에 추가.
    - [ ] P4.T 앱 실행 — 스텝 추가(예: go_back/wait)·순서변경·저장 후 재로드 유지 확인. 커밋: `feat(settings): dynamic flow builder tab`

- [ ] **P5 — settings UI: 설정 CSV 폴더 가져오기/내보내기**
    - [ ] P5.1 헤더에 **[설정 내보내기] [설정 불러오기]** 버튼. 내보내기=`getExistingDirectory` 선택 폴더에 각 CSV 저장(`export_config_to_dir`). 불러오기=`getExistingDirectory` 선택 폴더에서 `import_config_from_dir` → 반영 목록을 `QMessageBox` 로 요약 + `load()` 재호출로 UI 갱신.
    - [ ] P5.T 폴더로 export → 값 변경/초기화 → 같은 폴더 import 왕복으로 설정 복원 확인. 커밋: `feat(settings): import/export config as a shareable folder of CSVs`

---

### 적용 규칙 (요약)
- 신호/슬롯·스토리지 격리·디자인 토큰·테스트 격리(CLAUDE.md) 그대로. 실제 인스타/브라우저 호출 테스트 금지(MagicMock + storage patch).
- 매 커밋 후 `pytest tests/ -v` **전체 녹색** 확인 후 다음 단계.
- 커밋 메시지 끝: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.

---

## Verification (작업 완료 기준)
1. `cd src && .venv/bin/pytest tests/ -v` 전체 통과(신규 storage/flows 테스트 포함).
2. `cd src && .venv/bin/python main.py` → 설정: 버튼매핑 탭에 6스텝 이미지+가이드+셀렉터 표, 플로우 탭에서 스텝 추가/삭제/순서변경, [내보내기]→폴더 / [불러오기]→폴더 왕복.
3. 기본 flow_steps 로 수집 실행 시 기존 6스텝과 동일 동작(로그 prefix/신호 순서/dedup·필터·저장) — 회귀 없음.
