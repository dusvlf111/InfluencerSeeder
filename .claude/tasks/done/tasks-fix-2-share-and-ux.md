# Tasks: Fix 2 — 버튼매핑 자유화 / 수집필드 선택 / 로그인버튼 제거 / zip 선택 공유

> 사용자 요청(5건): ① 버튼매핑에서 가이드 이미지 제거 + 자유도 향상, ② 프로필에서 수집할 데이터 항목 선택 설정, ③ 메인화면 [로그인 완료] 버튼 제거(불필요), ④ 제외명단·수집데이터(results)도 내보내기/불러오기, ⑤ 내보내기 시 항목을 **체크박스로 선택**, 내보내기·불러오기는 **모두 zip(압축)**, 불러오면 압축 풀고 자동 적용.
> 상태: ✅ 완료 (A e320eae · B a38d6df · C 58382e9 · D be65be0 · 291 passed)
> 선행: 없음(현재 263 passed). 매 커밋 전체 green 유지.

---

### 실행 환경
- 사용 도구: Read, Write, Edit, Bash, Glob, Grep / 불가: Skill, Agent
- 테스트: `cd src && .venv/bin/pytest tests/ -v` (매 커밋 전체 — 현재 263)
- ⚠️ 실제 인스타/브라우저 호출 금지. UI 테스트는 conftest `qapp` + `monkeypatch DATA_DIR`. pytest-qt 없음(이벤트루프/실제 클릭 금지).
- git staging 본인 파일만(`git add <경로>`, `-A` 금지 — 무관 run_*.command/bat/README 존재).
- 커밋 끝: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`. 파트별 커밋.

### 참조 (작업 전 Read)
| 문서 | 용도 |
|------|------|
| `src/CLAUDE.md` | 신호/슬롯·스토리지·토큰·테스트 격리 규칙 |
| `src/ui/settings/mapping_tab.py` | 버튼매핑 카드(이미지 포함) — A |
| `src/ui/settings/flow_tab.py`, `src/ui/settings/__init__.py`, `src/ui/settings_view.py` | 설정 탭/믹스인 구조 — A·B |
| `src/core/flows/steps.py` (`ExtractProfile`) | 프로필 추출 — B |
| `src/core/storage*.py` (특히 storage_defaults/storage_config/storage_share/storage_results) | 설정 그룹·zip 공유·results — B·D |
| `src/ui/panels/control_panel.py`, `src/ui/main_window.py`, `src/ui/dialogs/login_dialog.py` | 로그인 버튼/다이얼로그 — C |
| `src/ui/settings/config_io.py` | 현행 폴더/파일 공유 — D(교체) |
| `src/tests/test_settings_view.py` | 매핑/공유 테스트(수정) |

### ⚠️ 계약
- 기존 신호 시그니처 불변(추가만). `core/scraper.py`·`core/storage.py` 모듈 유지. 파일 I/O 는 `core.storage` 만. 디자인 토큰만(hex 직접 금지). 위젯/스타일은 objectName + stylesheet.
- 매 파트 커밋 직후 `pytest tests/ -v` 전체 green. 깨진 기존 테스트는 신규 사양에 맞게 **수정**(삭제 금지, 커버리지 유지).

---

## A. 버튼매핑 — 이미지 제거 + 자유 편집 테이블

**현재:** step_id 그룹별 카드(스크린샷 + 가이드 + 후보표). 이미지가 크고 고정 step_id 중심이라 자유도 낮음.

**변경:** 카드/이미지를 없애고 **단일 자유 편집 테이블**로:
- 컬럼: `Step ID(편집) | Step Name | Priority | Type(xpath/css/coord) | Selector Value`.
- 버튼: [행 추가][행 삭제][위로][아래로][기본값으로 초기화]. **Step ID 를 자유 입력**(임의 step_id 추가 가능 → flow_steps 의 selector_ref 와 연동).
- 상단에 짧은 안내 라벨(이미지 없이): "브라우저에서 요소 우클릭 → 검사 → Copy → Copy XPath/selector. Type 은 xpath/css/coord."
- `mapping_tab.py` 의 `guide_image_for_selector`/`QPixmap`/`guideImage` 제거. `_build_mapping_card`/카드 구조 제거하고 `_build_mapping_tab` 을 단일 `QTableWidget` + 버튼으로 재작성.
- `_collect_selectors()` 는 **priority int 포함 list[dict]** 반환(기존 계약 유지 — `_save_all` 의 `save_selectors` 그대로 동작). `_populate_mapping(load_selectors())` 로 행 채움(priority 정렬). 빈 step_id 행은 저장 시 제외.
- ⚠️ `_save_all` 의 `save_selectors(self._collect_selectors())` 호출부 형태 유지. `assets.py`/`guide_image_*` 의존 제거(에셋 파일·`core/assets.py` 는 남겨도 무방, 단 mapping_tab 에서 import 안 함).
- T(`tests/test_settings_view.py`): 기존 `TestMappingCards`(`view._mapping_tables` 등 카드 전제) → 단일 테이블 사양으로 갱신: 행 추가/삭제/이동, `_collect_selectors` 가 priority int 포함 반환, 자유 step_id round-trip(`save_selectors`→`load_selectors`).
- **커밋:** `feat(settings): free-form button-mapping table (drop guide images)` ✅ e320eae

---

## B. 프로필 수집 필드 선택

**목표:** 어떤 프로필 필드를 수집/저장할지 사용자가 토글. `username` 은 필수(항상). 선택 대상: `full_name, followers, following, posts_count, bio, website, is_private`.

### B.1 storage: `fields.csv` (신규 설정 그룹)
- `storage_defaults.py`: `_FIELDS_DEFAULTS`(key,value) — 위 7개 필드 모두 `true`. `COLLECT_FIELDS: list[str]`(선택 가능한 필드명 순서).
- `storage_config.py`: `fields_defaults()/load_fields()->dict[str,bool]/save_fields(dict)` (kv 패턴, `_as`/bool 정규화는 `_truthy`/문자열 "true"/"false" 저장). facade re-export.
- T(`tests/test_storage.py`): 기본값/round-trip/누락 머지/손상 폴백.

### B.2 ExtractProfile 반영 (`core/flows/steps.py`)
- 생성자/ctx 어딘가에서 수집필드 dict 접근: ScraperThread 생성자에서 `self._collect_fields = (fields or storage.load_fields())` 주입(키워드 인자 `fields=None` 추가, 누락 시 self-load). 생성자 시그니처 확장은 **키워드 기본값**으로(기존 호출 호환).
- `ExtractProfile`: 비활성 필드는 **추출/저장 생략**(username 제외). 즉 result 에 비활성 필드 키를 넣지 않음(빈 칸으로 저장됨). 셀렉터 폴백(Fix-1 B)도 비활성 필드는 건너뜀.
- ⚠️ 기존 추출 테스트가 특정 필드를 단언하면, 기본(전부 true)에선 동일 동작 → 회귀 없음. 비활성 케이스 신규 테스트 추가.

### B.3 UI: 수집 항목 탭 (신규 믹스인 `ui/settings/fields_tab.py`)
- `FieldsTabMixin._build_fields_tab`: 필드별 `QCheckBox`(`_cf_<field>`), 라벨 한국어(이름/팔로워/팔로잉/게시물 수/소개/웹사이트/비공개여부). username 은 "항상 수집"으로 비활성 표시(체크 고정/disabled).
- `_populate_fields(load_fields())`, `_collect_fields_settings()->dict`. `SettingsView` 믹스인 목록·`_build_ui` addTab·`load`·`_save_all` 에 연결(저장은 `storage.save_fields`).
- T: 위젯 생성·populate·collect round-trip(`save_fields`→`load_fields`).
- **커밋:** `feat(settings):选 collectable profile fields (fields.csv) + ExtractProfile honors them`
  (한글/이모지 없이: `feat(settings): selectable profile collection fields (fields.csv)`) ✅ a38d6df

---

## C. 메인화면 [로그인 완료] 버튼 제거

**현재:** `control_panel` 에 `_btn_login_done`("로그인 완료") + `LoginWaitDialog` 둘 다 존재(중복). 다이얼로그에도 확인 버튼 있음.

**변경:**
- `control_panel.py` 에서 `_btn_login_done` 위젯 **제거**(btn_row 에서 빼기). `set_running(waiting_login=...)` 에서 해당 버튼 토글 코드 제거. `login_done_requested` 신호는 남겨도 되나 control_panel 에서 emit 안 하면 미사용 → **신호/연결 정리**(main_window 의 `_control.login_done_requested.connect` 도 제거). 로그인 확인은 **`LoginWaitDialog` 단독**으로 일원화(이미 `_on_waiting_login` 이 다이얼로그 생성·accepted→`_login_done`).
- `login_dialog.py` 문구 한국어화(선택): "인스타그램 로그인 — 브라우저에서 로그인 후 아래 [로그인 완료]" + 버튼 "로그인 완료".
- ⚠️ 로그인 대기 흐름 자체는 유지(다이얼로그로 확인). `main_window` 의 `_login_done`/`_on_waiting_login` 동작 보존.
- T(`tests/test_main_window.py`): control_panel 에 `_btn_login_done` 부재 확인 또는 기존 테스트가 그 버튼을 참조하면 갱신. `set_running` 호출이 예외 없이 동작.
- **커밋:** `feat(ui): remove redundant main-screen login button (dialog confirms login)` ✅ 58382e9

---

## D. zip 전용 + 체크박스 선택 공유 (설정 + 제외명단 + 수집데이터)

**목표:** 내보내기/불러오기를 **zip 단일 파일**로 통일. 내보낼 때 **체크박스로 항목 선택**(설정 CSV들 + `excluded.csv` 제외명단 + `results.csv` 수집데이터 + `fields.csv`). 불러오기는 zip 선택 → 압축 풀고 **자동 적용**.

### D.1 storage_share 확장
- 공유 대상에 데이터 파일 포함: `DATA_FILES = ["results.csv"]`. `SHAREABLE_FILES = CONFIG_FILES + DATA_FILES`(중복 없이; `fields.csv` 도 CONFIG_FILES 에 추가). 각 파일의 한국어 라벨 맵 `SHAREABLE_LABELS: dict[str,str]`(예: web.csv→"웹 설정", excluded.csv→"제외 명단", results.csv→"수집 데이터", selectors.csv→"버튼매핑", flow_steps.csv→"플로우", fields.csv→"수집 항목" 등).
- `export_config_to_zip(zip_path, names=None)`: `names` 기본 = `SHAREABLE_FILES`. results.csv/fields.csv 도 materialize 규칙 반영(results 는 존재 시만, loader None). `_CONFIG_LOADERS` 에 `fields.csv: "load_fields"`, `results.csv: None` 추가.
- `import_config_from_zip(zip_path)`: `SHAREABLE_FILES` 기준 basename 매칭(results.csv 포함). 기존 무-예외/CSV검증 유지.
- T(`tests/test_settings_view.py` 또는 test_storage): results.csv 포함 zip round-trip, fields.csv 포함, 선택 names 만 내보내기.

### D.2 내보내기 항목 선택 다이얼로그 (`ui/dialogs/export_select_dialog.py` 신규)
- `ExportSelectDialog(QDialog)`: `SHAREABLE_FILES` 각 항목 체크박스(라벨=`SHAREABLE_LABELS`, 기본 전체 체크; 존재하지 않는 파일은 회색/해제). [전체선택][전체해제][내보내기][취소]. `selected_names()->list[str]` 반환. 디자인 토큰/objectName.

### D.3 config_io 교체 (zip 전용 2버튼)
- `config_io.py`: 폴더 기반 `_export_config`/`_import_config` 및 기존 파일 핸들러를 **zip 전용**으로 정리:
  - `_export_config()`: `ExportSelectDialog` 띄워 선택 → `QFileDialog.getSaveFileName(...zip)` → `storage.export_config_to_zip(path, names=selected)` → 결과 QMessageBox.
  - `_import_config()`: `QFileDialog.getOpenFileName(...zip)` → `storage.import_config_from_zip(path)` → `self.load()` + `self.imported.emit()` → 반영 목록 QMessageBox.
- `settings_view.py` 헤더 버튼을 **2개**로: "설정·데이터 내보내기"(→`_export_config`), "불러오기"(→`_import_config`). 기존 4버튼(폴더/파일) 제거. 폴더용 storage 헬퍼(`export_config_to_dir`/`import_config_from_dir`)는 남겨도 되나 UI 에서 미사용.
- ⚠️ import 후 results 반영 시 메인뷰 결과 패널 갱신은 `imported` 신호로 처리(필요하면 main_window 가 results 재로딩 — 범위 밖이면 메시지로만 안내).
- T: 다이얼로그 select 로직(헤드리스 — `selected_names` 단위), config_io 는 storage 헬퍼 경유라 storage 테스트로 커버. QFileDialog/모달 직접 호출 금지.
- **커밋:** `feat(settings): zip-only export/import with per-item checkboxes (settings + excluded + results)` ✅ be65be0

---

## 완료 보고
- A/B/C/D 각 구현 요약 + 커밋 해시, 최종 `pytest tests/ -v` 통과 개수
- 신규 파일(fields_tab.py, export_select_dialog.py, fields.csv 스키마), 변경 요약
- 사용자 라이브 확인 항목(버튼매핑 자유표·수집항목 토글·로그인 흐름·zip 내보내기 체크박스/불러오기 자동적용)
