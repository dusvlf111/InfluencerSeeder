# Tasks: Refactor 3 — settings_view.py 모듈화 (990줄 → 믹스인 분리)

> 목적: `ui/settings_view.py`(990줄)를 탭별 **Mixin 클래스**로 분리해 500줄 미만으로. 사용자 상시 규칙("500줄 이상 모두 리팩터링").
> 상태: ✅ 완료 (settings_view.py 990→143줄, 9개 *TabMixin 분리, 242 passed)
> 선행: flow-builder 완료(현재). 후행: 없음(마지막 작업).

---

### 실행 환경
- **사용 가능 도구:** Read, Write, Edit, Bash, Glob, Grep
- **사용 불가 도구:** Skill, Agent
- **테스트:** `cd src && .venv/bin/pytest tests/ -v` (매 커밋마다 전체 — 242개 유지)
- **병렬 작업:** 불가

### 참조 문서 (작업 전 Read)
| 문서 | 용도 |
|------|------|
| `src/ui/settings_view.py` | 분리 대상 (990줄) |
| `src/tests/test_settings_view.py` | **계약의 원천** — `view._w_browser`/`view._collect_delays`/`view._flow_table`/`view._mapping_tables`/`view._flow_add_row` 등 SettingsView 의 **메서드·속성을 직접 참조**. 분리 후에도 전부 `self` 에 남아야 함 |
| `src/CLAUDE.md` | 디자인 토큰·UI↔스토리지 분리·테스트 격리 규칙 |

---

### ⚠️ 절대 깨면 안 되는 계약
1. **`SettingsView` 인스턴스에서 기존 메서드·속성이 그대로 접근 가능해야 함.** 테스트가 `view._w_browser`, `view._delay_table`, `view._flow_table`, `view._mapping_tables`, `view._fl_max_tags`, `view._t_mode`, `view._collect_web/_collect_delays/_collect_flow/_collect_target/_collect_selectors/_collect_flow_steps`, `view._mapping_add_row/_mapping_del_row/_mapping_move_row`, `view._flow_add_row/_flow_del_row/_flow_move_row/_flow_reset`, `view._selector_ref_choices`, `view._add_excluded`, `view._save_all`, `view.load`, `view._tabs`, `view.back_requested` 등을 직접 호출/참조한다.
2. → **Mixin 방식 사용.** 탭별 메서드를 `*TabMixin` 클래스(plain class, QWidget 상속 X)로 옮기고 `class SettingsView(QWidget, WebTabMixin, DelaysTabMixin, ...)` 로 다중상속. 메서드는 `self`(=SettingsView 인스턴스)에서 동작하며 `self._x = ...` 속성을 그대로 세팅 → 테스트 참조 유지.
3. **위젯 분리(각 탭을 독립 QWidget 으로) 금지** — 속성이 SettingsView 에서 떨어져 나가 테스트가 깨진다.
4. 신호(`back_requested`, `imported`)는 `SettingsView`(QWidget)에 정의 유지. Mixin 메서드는 `self.back_requested.emit()` 처럼 호출(런타임에 self 가 SettingsView 라 동작).
5. 파일 I/O·디자인토큰 규칙 유지(파일 I/O 는 `core.storage`, hex 직접 금지).
6. 매 커밋 후 `pytest tests/ -v` 전체 통과(242) 확인 후 다음 단계.

---

## 목표 구조
```
ui/settings_view.py            # SettingsView(QWidget, *Mixins): 신호 + __init__ + _build_ui + load + _populate + _save_all (코디네이터, ≤ ~180줄)
ui/settings/__init__.py
ui/settings/web_tab.py         # WebTabMixin: _build_web_tab/_populate_web/_collect_web
ui/settings/delays_tab.py      # DelaysTabMixin: _build_delays_tab/_populate_delays/_collect_delays
ui/settings/flow_tab.py        # FlowTabMixin: _build_flow_tab/_populate_flow/_collect_flow
ui/settings/target_tab.py      # TargetTabMixin: _build_target_tab/_populate_target/_collect_target
ui/settings/mapping_tab.py     # MappingTabMixin: _build_mapping_tab/_build_mapping_card/_populate_mapping/_mapping_set_row/_collect_selectors/_mapping_add_row/_mapping_del_row/_mapping_move_row
ui/settings/flowbuilder_tab.py # FlowBuilderTabMixin: _build_flowbuilder_tab/_flow_insert_step_row/_flow_renumber/_flow_add_row/_flow_del_row/_flow_move_row/_flow_reset/_flow_collect_row/_populate_flow_steps/_collect_flow_steps/_selector_ref_choices
ui/settings/excluded_tab.py    # ExcludedTabMixin: _build_excluded_tab/_populate_excluded/_collect_excluded/_add_excluded/_remove_excluded
ui/settings/deps_tab.py        # DepsTabMixin: _build_deps_tab/_run_pip
ui/settings/config_io.py       # ConfigIOMixin: _export_config/_import_config
```
- `SettingsView._build_ui` 는 그대로 `self._build_web_tab()` 등을 호출(메서드는 믹스인에서 제공). `load`→`self._populate_*`, `_save_all`→`self._collect_*`+`storage.save_*` 유지.
- 각 믹스인 파일은 자신이 쓰는 PyQt 위젯·`core.storage`·`design` 토큰을 import. 모듈 함수(`_as_bool`, `_mapping_set_row`(staticmethod) 등)는 적절한 믹스인/모듈에 배치하되 기존 호출부에서 접근 가능하게.

---

## 작업

- [x] R3.0 settings_view 믹스인 분리 (전 범위)

    - [x] R3.1 `ui/settings/` 패키지 + Web/Delays/Flow/Target 믹스인 추출
        **작업 상세:** 위 4개 탭의 `_build_*_tab`/`_populate_*`/`_collect_*` 를 각 믹스인 파일로 이동. `SettingsView` 가 해당 믹스인 상속. `_as_bool` 등 공용 헬퍼는 `ui/settings/__init__.py` 또는 공용 모듈에 두고 import.
        - [x] R3.1.T1 `pytest tests/ -v` → 242 passed (TestAsBool/TestTabsAndPopulate/TestSaveAll).
        - [x] R3.1 커밋: `refactor(settings): extract web/delays/flow/target tab mixins` (f7b5aff)

    - [x] R3.2 Mapping(버튼매핑) 믹스인 추출
        **작업 상세:** `_build_mapping_tab/_build_mapping_card/_populate_mapping/_mapping_set_row/_collect_selectors/_mapping_add_row/_mapping_del_row/_mapping_move_row` 및 `_mapping_tables`/`_mapping_names` 상태를 `mapping_tab.py` 로. 가이드 이미지(`guide_image_for_selector`) 헬퍼 포함.
        - [x] R3.2.T1 `pytest tests/ -v` → 242 passed (TestMappingCards).
        - [x] R3.2 커밋: `refactor(settings): extract button-mapping tab mixin` (e7ded62)

    - [x] R3.3 FlowBuilder 믹스인 추출
        **작업 상세:** `_build_flowbuilder_tab/_flow_*/_populate_flow_steps/_collect_flow_steps/_selector_ref_choices` 를 `flowbuilder_tab.py` 로. `_flow_table` 속성 유지.
        - [x] R3.3.T1 `pytest tests/ -v` → 242 passed (TestFlowBuilder).
        - [x] R3.3 커밋: `refactor(settings): extract flow-builder tab mixin` (4fb2b53)

    - [x] R3.4 Excluded/Deps/ConfigIO 믹스인 + 최종 정리
        **작업 상세:** `_build_excluded_tab/_add_excluded/_remove_excluded/_collect_excluded/_populate_excluded` → `excluded_tab.py`; `_build_deps_tab/_run_pip` → `deps_tab.py`; `_export_config/_import_config` → `config_io.py`. `SettingsView` 에는 신호·`__init__`·`_build_ui`·`load`·`_populate`·`_save_all` 만 남긴다. `wc -l` 로 settings_view.py 및 각 믹스인 < 500 확인(settings_view.py 목표 ≤ ~180).
        - [x] R3.4.T1 `pytest tests/ -v` → 242 passed. `cd src && .venv/bin/python -c "import ui.settings_view"` import 스모크. (settings_view.py 143줄)
        - [x] R3.4 커밋: `refactor(settings): extract excluded/deps/config-io mixins; settings_view is a coordinator` (f265d97)

---

### 적용 규칙
- 신호/슬롯·디자인토큰·UI↔스토리지 분리·테스트 격리(CLAUDE.md) 그대로.
- 커밋 메시지 끝: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.
- git staging 시 **본인 파일만**(`git add <경로>`). `git add -A` 금지(작업트리에 무관한 run_*.command/bat 존재).
