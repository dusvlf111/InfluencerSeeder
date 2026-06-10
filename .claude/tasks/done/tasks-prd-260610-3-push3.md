# Tasks: InfluencerSeeder v3 - Push 3 (설정 UI 기본 탭 — 웹/시간텀/플로우/타겟/제외)

> PRD: `.claude/tasks/prd-260610-3.md` (§2 설정 5그룹, §9 `ui/settings_view.py`)
> Push 범위: `ui/settings_view.py` QTabWidget **기본 4탭(웹/시간텀/플로우/타겟) + 제외 탭** + populate/collect/save_all 배선.
> 상태: 🔲 진행 중
> 선행: **Push 1 완료 필수** (storage `load_web/load_delays/load_flow/load_target/save_*`).
>
> ⚠️ **병합 결정(2026-06-10):** 버튼매핑/플로우 탭·셀렉터 테스트·설정 import/export 는 `tasks-260610-4-flow-builder.md`
> (카드형 버튼매핑 P3 / 플로우 빌더 P4 / 폴더형 import/export P5)가 담당한다.
> 따라서 이 Push 는 **셀렉터 탭을 만들지 않고**, 위 5개 설정 그룹 기본 탭만 구축한다(중복 제거).
> flow-builder 가 이후 같은 `SettingsView` 에 버튼매핑·플로우 탭과 헤더 import/export 버튼을 추가한다.

---

### 실행 환경

- **사용 가능 도구:** Read, Write, Edit, Bash, Glob, Grep, Task
- **사용 불가 도구:** Skill, Agent
- **테스트 실행:** `cd src && .venv/bin/pytest tests/test_settings_view.py -v`
- **전체 테스트:** `cd src && .venv/bin/pytest tests/ -v`
- **앱 실행(수동 확인):** `cd src && .venv/bin/python main.py`
- **병렬 작업:** 불가
- ⚠️ **pytest-qt 미설치.** UI 테스트는 모듈 레벨 `QApplication` fixture(아래 규칙 참조)로 위젯을 생성하고, **순수 로직(collect/populate/parse) 위주**로 검증. 이벤트 루프·실제 클릭 시뮬레이션은 피한다.

### 참조 이미지

| 이미지 | 용도 | 관련 작업 |
|--------|------|-----------|
| `.claude/tasks/1_돋보기 클릭.png` | 버튼매핑 탭 search_icon 행 편집 예시 | 3.2 |
| `.claude/tasks/6_프로필 이미지에서 정보 저장.png` | 타겟 탭 필터 항목(팔로워/팔로우/게시물) 매핑 | 3.1 |

### 참조 문서

작업 시작 전 반드시 `Read`로 읽을 것:

| 문서 | 용도 |
|------|------|
| `.claude/tasks/prd-260610-3.md` | §2 5그룹 스키마, §2.2 셀렉터 테스트 버튼, §7 Import/Export, §9 settings_view |
| `src/ui/settings_view.py` | 기존 SettingsView QTabWidget·탭 빌더·populate/collect (수정 대상) |
| `src/core/storage.py` | Push1 신규 load/save 함수 시그니처 (이 Push 가 호출) |
| `src/design/tokens.py` | 색상/타이포/여백 토큰 — QSS·objectName 작성 시 참조 |
| `src/ui/main_window.py` | SettingsView 사용처(`show_settings` → `load()`) — 호환 확인 |

### 적용 규칙 (프로젝트 컨벤션)

#### 디자인 토큰 / 스타일
- 색상·여백은 `design/tokens.py` 의 `Colors.*`/`Spacing.*`/`Radius.*` 만 사용. **QSS 리터럴에 hex 직접 작성 금지.**
- 스타일 적용은 기존처럼 `objectName`(`btnPrimary`, `labelMuted`, `labelAccent`, `settingsHeader` 등) 부여 후 전역 스타일시트(`design/stylesheet.py`)가 처리하는 방식. 새 objectName 필요 시 의미있게 명명.
- 위젯 구성은 기존 `_build_*_tab()` 패턴(QVBoxLayout/QFormLayout, `setContentsMargins`, `setSpacing`) 따르기.

#### UI ↔ 스토리지 분리
- 파일 I/O 는 절대 settings_view 에서 직접 하지 않고 `core.storage` 함수 호출.
- `load()` 에서 모든 CSV 읽어 위젯 채움(`_populate`), `_save_all()` 에서 위젯값 수집(`_collect_*`) 후 `storage.save_*`.
- 한 탭 = 한 설정 그룹 = 한 CSV. populate/collect 를 그룹별 메서드로 분리.

#### 신호/슬롯
- `back_requested = pyqtSignal()` 유지. 저장 성공 시 `back_requested.emit()`(기존 동작).
- Import 완료 시 메인뷰가 재로딩하도록 신규 신호 `imported = pyqtSignal()` 추가 가능(main_window 가 연결, Push4 와 협의 — 이 Push 에서 신호 정의 + emit 까지).

#### 테스트 격리 (pytest)
- 모듈 상단에 `QApplication` 공유 fixture:
  ```python
  import pytest
  from PyQt6.QtWidgets import QApplication
  @pytest.fixture(scope="session")
  def qapp():
      app = QApplication.instance() or QApplication([])
      yield app
  ```
- `storage` 는 `monkeypatch.setattr(storage, "DATA_DIR", tmp_path)` 로 격리(파일 실제 생성 가능).
- 위젯 생성 후 `view._collect_*()`/`_populate()` 결과를 검증. 실제 사용자 클릭은 메서드 직접 호출로 대체.

### 관련 파일

- `src/ui/settings_view.py` — SettingsView (수정 대상)
- `src/core/storage.py` — Push1 함수 호출 (수정 안 함)
- `src/design/tokens.py` / `src/design/stylesheet.py` — 스타일 토큰
- `src/tests/test_settings_view.py` — 테스트 (신규 생성)

---

## 작업

> **병합 범위:** 이 Push 는 **웹/시간텀/플로우/타겟/제외** 5개 탭만 만든다. **셀렉터(버튼매핑) 탭은 만들지 않는다** — flow-builder P3 가 카드형으로 구축. 단, 기존 settings_view 에 이미 있는 Selectors 탭은 **제거하지 말고 그대로 둔다**(flow-builder 가 교체). `save_selectors` 호출도 건드리지 않는다.

- [x] 3.0 SettingsView 기본 설정 탭 (Push 범위)

    - [x] 3.1 기본 탭 구조 + load/populate 분리
        **작업 상세:** §2. `_build_ui` 의 탭 구성에 **웹 / 시간텀 / 플로우 / 타겟 / 제외** 탭을 구축한다(기존 Collection→타겟/플로우로 분해, Delays→시간텀, Excluded 유지, Dependencies 는 유지 또는 제거 판단). **기존 Selectors 탭은 그대로 유지**(flow-builder P3 가 버튼매핑 카드로 교체 예정 — 지금 손대지 말 것).
        탭별 빌더:
        - `_build_web_tab`(§2.1: browser/headless/window_width/height/randomize_window/randomize_user_agent/user_data_dir/locale/implicit_wait/page_load_timeout — QComboBox/QCheckBox/QSpinBox/QLineEdit 적절히)
        - `_build_delays_tab`(시간텀 — 기존 표 + `scroll`/`typing_char` 행 추가, `load_delays()` 의 `{step_id:(min,max)}` 형태 반영)
        - `_build_flow_tab`(§2.4: max_tags/tag_start_index/posts_per_tag/scroll_max_attempts/skip_visited_profile(체크박스)/stop_on_consecutive_miss)
        - `_build_target_tab`(§2.5: min/max_followers·following, min_posts, keyword, mode)
        - `_build_excluded_tab`(기존 유지)
        `load()` 가 `storage.load_web/load_delays/load_flow/load_target/load_excluded`(+ 기존 load_selectors 유지) 호출하도록 교체. `_populate` 를 그룹별 메서드로 분리.
        **참조:** PRD §2, 이미지 `6_프로필 이미지에서 정보 저장.png`, `src/ui/settings_view.py`, `src/design/tokens.py`
        - [x] 3.1.T1 pytest (`tests/test_settings_view.py`, `class TestTabsAndPopulate`): qapp+tmp DATA_DIR 로 `SettingsView()` 생성·`load()` 호출 시 예외 없음, 웹/시간텀/플로우/타겟/제외 탭 위젯 존재, web/flow/target 위젯이 storage 기본값으로 채워짐(예: headless 체크 해제, max_tags=3, mode=hashtag).
        - [x] 3.1.T2 `cd src && .venv/bin/pytest tests/test_settings_view.py::TestTabsAndPopulate -v` 실행 및 검증

    - [x] 3.2 _save_all 통합 + collect (web/delays/flow/target/excluded)
        **작업 상세:** `_save_all()` 이 `storage.save_web/save_delays/save_flow/save_target/save_excluded` 를 호출하도록 통합(+ 기존 `save_selectors`/`save_settings` 호출은 그대로 유지). 각 `_collect_web/_collect_delays/_collect_flow/_collect_target/_collect_excluded` 구현. `_collect_delays` 는 `{step_id:(min,max)}` dict 로 반환. 저장 실패 시 `QMessageBox.critical`(기존 패턴). 성공 시 `back_requested.emit()`.
        ⚠️ 셀렉터 collect/save 는 기존 코드 그대로(flow-builder 영역).
        **참조:** `src/ui/settings_view.py` (`_save_all`, `_collect_*`)
        - [x] 3.2.T1 pytest (`class TestSaveAll`): 위젯값 세팅 후 `_save_all` 호출 → tmp DATA_DIR 에 web/delays/flow/target/excluded CSV 생성·값 round-trip(`storage.load_*` 로 재확인), 잘못된 숫자 입력 시 예외 전파 없이 처리.
        - [x] 3.2.T2 `cd src && .venv/bin/pytest tests/test_settings_view.py::TestSaveAll -v` 실행 및 검증

    - [x] 3.3 전체 회귀 + 스모크
        **작업 상세:** `cd src && .venv/bin/pytest tests/ -v` 전체 통과(기존 185 + 신규 settings 테스트). 헤드리스면 `SettingsView` 생성·`load()`·`_save_all()` 스모크로 대체하고 사유 기록.
        - [x] 3.3.T1 `cd src && .venv/bin/pytest tests/ -v` 전체 통과 확인 (212 passed = 기존 185 + 신규 27)
