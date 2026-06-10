# Tasks: InfluencerSeeder v3 - Push 3 (설정 UI 6탭 재편 + Import/Export + 셀렉터 테스트)

> PRD: `.claude/tasks/prd-260610-3.md` (§2 설정 5그룹, §7 공유, §9 `ui/settings_view.py`)
> Push 범위: `ui/settings_view.py` QTabWidget 6탭(웹/버튼매핑/시간텀/플로우/타겟/제외) + 행 추가·삭제·priority 정렬 + [셀렉터 테스트] + [설정 불러오기]/[설정 내보내기]
> 상태: 🔲 진행 중
> 선행: **Push 1 완료 필수** (storage `load_web/load_selectors/load_delays/load_flow/load_target/save_*`). Push 2 와 독립이나 권장 순서상 2 이후.

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

- [ ] 3.0 SettingsView 6탭 재편 (Push 범위)

    - [ ] 3.1 6탭 구조 재편 + load/populate 분리
        **작업 상세:** §2. `_build_ui` 의 탭 구성을 **웹 / 버튼매핑 / 시간텀 / 플로우 / 타겟 / 제외** 6탭으로 교체(기존 Collection/Delays/Selectors/Excluded/Dependencies 재편 — Dependencies 는 유지 또는 제거 판단, PRD 6탭 기준).
        탭별 빌더: `_build_web_tab`(§2.1 키: browser/headless/window_width/height/randomize_window/randomize_user_agent/user_data_dir/locale/implicit_wait/page_load_timeout — QComboBox/QCheckBox/QSpinBox/QLineEdit 적절히), `_build_selectors_tab`(3.2), `_build_delays_tab`(시간텀 — 기존 표 + scroll/typing_char 행 추가), `_build_flow_tab`(§2.4), `_build_target_tab`(§2.5), `_build_excluded_tab`(기존 유지).
        `load()` 가 `storage.load_web/load_selectors/load_delays/load_flow/load_target/load_excluded` 호출하도록 교체. `_populate` 를 그룹별로 분리.
        **참조:** PRD §2, 이미지 `6_프로필 이미지에서 정보 저장.png`, `src/ui/settings_view.py`, `src/design/tokens.py`
        - [ ] 3.1.T1 pytest (`tests/test_settings_view.py`, `class TestTabsAndPopulate`): qapp+tmp DATA_DIR 로 `SettingsView()` 생성·`load()` 호출 시 예외 없음, 탭 개수==6, 각 탭 위젯 존재, web/flow/target 위젯이 storage 기본값으로 채워짐.
        - [ ] 3.1.T2 `cd src && .venv/bin/pytest tests/test_settings_view.py::TestTabsAndPopulate -v` 실행 및 검증

    - [ ] 3.2 버튼매핑 탭 — 행 추가/삭제 + priority 컬럼/정렬
        **작업 상세:** §2.2. 셀렉터 표 컬럼을 `Step ID | Step Name | Priority | Type | Selector Value` 5열로 확장. **[행 추가]**(현재 선택 step_id 기반 새 후보 행), **[행 삭제]**, **[priority 정렬]**(step_id→priority 오름차순 재정렬) 버튼 추가.
        `_collect_selectors()` 가 priority(int) 포함 dict 리스트 반환. `_save_all` 이 `storage.save_selectors` 로 저장. `_reset_selectors` 는 `storage.selector_defaults()` 사용.
        **참조:** PRD §2.2, 이미지 `1_돋보기 클릭.png`, `src/ui/settings_view.py` (`_build_selectors_tab`, `_collect_selectors`)
        - [ ] 3.2.T1 pytest (`class TestSelectorRows`): 행 추가 메서드 호출 시 rowCount 증가, 행 삭제 시 감소, priority 정렬 메서드가 step_id별 priority 오름차순 배치, `_collect_selectors` 가 priority int 포함 반환.
        - [ ] 3.2.T2 `cd src && .venv/bin/pytest tests/test_settings_view.py::TestSelectorRows -v` 실행 및 검증

    - [ ] 3.3 [셀렉터 테스트] 버튼 — 매칭 개수 표시
        **작업 상세:** §2.2. 버튼매핑 탭에 **[셀렉터 테스트]** 버튼. 현재 선택 행의 `selector_type/value` 로, **열려있는 드라이버가 있으면**(메인에서 주입받은 driver 참조 or 콜백 신호) `find_elements` 매칭 개수를 메시지로 표시. 드라이버 없으면 "실행 중 브라우저 없음" 안내(QMessageBox).
        구현 단순화: settings_view 가 직접 selenium 을 들지 않도록, `selector_test_requested = pyqtSignal(str, str)`(type, value) 신호만 emit 하고 결과는 `show_selector_test_result(count:int)` 슬롯으로 표시. 실제 매칭은 main_window/scraper 가 처리(Push4 와 연계, 이 Push 는 신호+슬롯+UI 까지).
        **참조:** PRD §2.2
        - [ ] 3.3.T1 pytest (`class TestSelectorTest`): 선택 행 없을 때 안전(예외 없음), 행 선택 후 테스트 트리거 시 `selector_test_requested` 가 올바른 (type,value)로 emit(QSignalSpy 대신 신호 연결 후 콜백 리스트 캡처), `show_selector_test_result(3)` 호출 시 예외 없음.
        - [ ] 3.3.T2 `cd src && .venv/bin/pytest tests/test_settings_view.py::TestSelectorTest -v` 실행 및 검증

    - [ ] 3.4 [설정 불러오기]/[설정 내보내기] — Import/Export
        **작업 상세:** §7. 헤더 바에 **[설정 불러오기] [설정 내보내기]** 버튼 추가.
        Export: 각 CSV 를 사용자가 고른 폴더로 `shutil.copy`(storage 에 `export_config(dest_dir)` 헬퍼 추가 또는 settings_view 가 `storage.DATA_DIR` 의 파일 목록 복사). 대상 파일: web/selectors/delays/flow/target/excluded/results.
        Import: `QFileDialog` 로 폴더 선택 → 해당 폴더의 동명 CSV 를 `DATA_DIR` 로 교체 복사 후 `load()` 재호출 + `imported.emit()`. 파일 I/O 는 storage 헬퍼(`import_config(src_dir)`/`export_config(dest_dir)`)에 두는 것을 권장(테스트 용이).
        **참조:** PRD §7, `src/core/storage.py` (`export_results`/`shutil` 패턴)
        - [ ] 3.4.T1 pytest (`class TestImportExport`, **storage 헬퍼 단위 테스트로 검증**): tmp DATA_DIR 에 CSV 생성 → `export_config(dest)` 후 dest 에 동일 파일 존재, `import_config(src)` 후 DATA_DIR 내용 교체 확인. (QFileDialog 는 테스트 안 함 — 헬퍼만.)
        - [ ] 3.4.T2 `cd src && .venv/bin/pytest tests/test_settings_view.py::TestImportExport -v` 실행 및 검증

    - [ ] 3.5 _save_all 통합 + collect 전부 연결
        **작업 상세:** `_save_all()` 이 `storage.save_web/save_selectors/save_delays/save_flow/save_target/save_excluded` 를 모두 호출하도록 통합. 각 `_collect_web/_collect_delays/_collect_flow/_collect_target/_collect_selectors/_collect_excluded` 구현. 저장 실패 시 `QMessageBox.critical`(기존 패턴). 성공 시 `back_requested.emit()`.
        **참조:** `src/ui/settings_view.py` (`_save_all`, `_collect_*`)
        - [ ] 3.5.T1 pytest (`class TestSaveAll`): 위젯값 세팅 후 `_save_all` 호출 → tmp DATA_DIR 에 6개 CSV 생성·값 round-trip(load 로 재확인), 잘못된 숫자 입력 시 예외 전파 없이 처리.
        - [ ] 3.5.T2 `cd src && .venv/bin/pytest tests/test_settings_view.py::TestSaveAll -v` 실행 및 검증

    - [ ] 3.6 전체 회귀 + 수동 스모크
        **작업 상세:** `cd src && .venv/bin/pytest tests/ -v` 통과. 가능하면 `.venv/bin/python main.py` 로 설정 화면 6탭 렌더 육안 확인(헤드리스 환경이면 생략하고 사유 기록).
        - [ ] 3.6.T1 `cd src && .venv/bin/pytest tests/ -v` 전체 통과 확인
