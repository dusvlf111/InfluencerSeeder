# Tasks: Refactor 2 — storage.py 모듈화 (508줄 → 관심사 분리)

> 목적: `core/storage.py`(508줄)를 **데이터(defaults) / 설정그룹 / 셀렉터 / 결과·제외 / 상태** 모듈로 분리.
> `DATA_DIR` monkeypatch 테스트 계약을 절대 깨지 않도록 storage.py 를 **파사드 모듈**로 유지한다.
> 상태: 🔲 진행 중
> 선행: Refactor 1 완료 권장(독립적이라 순서 무관하나 순차 실행).

---

### 실행 환경
- **사용 가능 도구:** Read, Write, Edit, Bash, Glob, Grep
- **사용 불가 도구:** Skill, Agent
- **테스트:** `cd src && .venv/bin/pytest tests/ -v` (매 커밋마다 전체 실행)
- **병렬 작업:** 불가

### 참조 문서 (작업 전 반드시 Read)
| 문서 | 용도 |
|------|------|
| `src/core/storage.py` | 분리 대상 원본 (508줄) |
| `src/tests/test_storage.py` | DATA_DIR monkeypatch 계약 (autouse `tmp_data_dir`) |
| `src/tests/test_scraper_utils.py` | `patch("core.storage.save_state")` 등 storage 이름 patch 계약 |
| `src/CLAUDE.md` | 스토리지 격리·테스트 격리 규칙 |

---

### ⚠️ 절대 깨면 안 되는 계약

1. **`core/storage.py` 는 `.py` 모듈(파사드)로 유지.** 패키지로 바꾸지 말 것.
2. `monkeypatch.setattr(storage, "DATA_DIR", tmp_path)` (storage = `core.storage`) 가 **모든** load/save 에 적용돼야 함.
   → **`DATA_DIR` 와 모든 경로 해석 프리미티브는 `core/storage.py` 안에만** 둔다.
     분리된 sibling 모듈은 **DATA_DIR 을 직접 참조하지 않고**, storage.py 의 프리미티브(`_path`/`_load_kv`/`_save_kv`/`_ensure_data_dir`/`results_path`)를 통해서만 파일에 접근한다.
3. 다음 이름들이 `core.storage` 에서 그대로 호출 가능해야 함(테스트·소비자):
   `DATA_DIR, load_settings, save_settings, settings_defaults, load_web, save_web, web_defaults,
    load_flow, save_flow, flow_defaults, load_target, save_target, target_defaults,
    load_delays, save_delays, delay_defaults, load_selectors, save_selectors, selector_defaults,
    load_excluded, save_excluded, load_results, append_result, seen_usernames, export_results, results_path,
    load_state, save_state, clear_state`
   → sibling 로 옮긴 함수는 storage.py 에서 **re-export**(`from core.storage_x import ...`).
4. `patch("core.storage.save_state")` 가 `ScraperThread._save_state`(`from core import storage; storage.save_state(...)`)에 영향.
   → `save_state` 가 `core.storage` 네임스페이스에 re-export 되어 있으면 동적 조회라 OK(이미 thread 가 `storage.save_state` 로 호출).
5. 매 커밋 후 `pytest tests/ -v` 전체 통과(현재 124 + Refactor1 신규분) 확인 후 다음 단계.

---

## 목표 구조

```
core/
  storage.py            # 파사드: DATA_DIR, _ensure_data_dir, _path(filename),
                        #   _coerce, _kv_defaults, _load_kv, _save_kv, _load_rows, _save_rows,
                        #   results_path()  + 모든 그룹 함수 re-export
  storage_defaults.py   # 순수 데이터: _SETTINGS/_WEB/_FLOW/_TARGET/_DELAY_DEFAULTS,
                        #   _SELECTOR_DEFAULTS, _RESULTS_FIELDNAMES, _SELECTOR_FIELDNAMES (DATA_DIR 무관)
  storage_config.py     # settings/web/flow/target/delays: *_defaults / load_* / save_*
  storage_selectors.py  # selector_defaults / _normalize_selector_row / load_selectors / save_selectors
  storage_results.py    # results_path*/load_results/append_result/seen_usernames/export_results
                        #   + load_excluded/save_excluded
  storage_state.py      # load_state/save_state/clear_state
```

순환참조 회피: sibling 은 `from core import storage as _st` 후 함수 **내부**에서 `_st._path(...)`/`_st._load_kv(...)` 호출(import 시점엔 미참조). storage.py 는 프리미티브 정의 **후 맨 아래**에서 sibling 을 import 해 re-export.
defaults 는 `from core.storage_defaults import ...` 로 storage.py·sibling 양쪽이 공유(순환 없음).

> `_path(filename)` 신규 프리미티브: `_ensure_data_dir(); return DATA_DIR / filename`. 기존 직접 경로 접근(`DATA_DIR / "x.csv"`)을 전부 `_path("x.csv")` 로 치환하면 DATA_DIR 단일 출처가 보장됨.

---

## 작업

- [x] R2.0 storage 모듈화 (전 범위)

    - [x] R2.1 `storage_defaults.py` + `_path` 프리미티브 도입
        **작업 상세:** 모든 `_*_DEFAULTS`·`_RESULTS_FIELDNAMES`·`_SELECTOR_FIELDNAMES` 를 `core/storage_defaults.py` 로 이동(순수 데이터). storage.py 는 `from core.storage_defaults import *`(또는 명시 import). storage.py 에 `_path(filename)` 추가하고, 기존 `DATA_DIR / "..."` 직접 접근을 `_path(...)` 로 치환(load_settings/delays/selectors/excluded/state/results 전부). 동작 불변.
        - [x] R2.1.T1 `pytest tests/ -v` 전체 통과(데이터 이동·_path 치환 후 동작 동일).
        - [x] R2.1 커밋: `refactor(storage): extract defaults data + introduce _path primitive`

    - [x] R2.2 `storage_state.py` 분리
        **작업 상세:** `load_state/save_state/clear_state` 를 `core/storage_state.py` 로 이동(함수 내부에서 `_st._path("state.json")`·`_st._ensure_data_dir()` 사용). storage.py 에서 re-export.
        - [x] R2.2.T1 `pytest tests/ -v` (특히 `TestState`, `TestResumeAndState`의 `patch("core.storage.save_state")`).
        - [x] R2.2 커밋: `refactor(storage): split state.json IO into storage_state.py`

    - [x] R2.3 `storage_results.py` 분리
        **작업 상세:** `results_path/load_results/append_result/seen_usernames/export_results` + `load_excluded/save_excluded` 를 `core/storage_results.py` 로 이동. storage 프리미티브 경유. storage.py re-export. ⚠️ `append_result`/`seen_usernames` 의 dedup·정규화 동작 불변. (참고: `results_path` 는 절대 원칙상 경로 프리미티브로 storage.py 에 잔류, sibling 은 `_st.results_path()` 경유.)
        - [x] R2.3.T1 `pytest tests/ -v` (특히 `TestResultsDedup`, `TestExcluded`).
        - [x] R2.3 커밋: `refactor(storage): split results/excluded IO into storage_results.py`

    - [x] R2.4 `storage_selectors.py` 분리
        **작업 상세:** `selector_defaults/_normalize_selector_row/load_selectors/save_selectors` 를 `core/storage_selectors.py` 로 이동. priority 정렬 동작 불변. storage.py re-export.
        - [x] R2.4.T1 `pytest tests/ -v` (특히 `TestSelectors`).
        - [x] R2.4 커밋: `refactor(storage): split selectors IO into storage_selectors.py`

    - [x] R2.5 `storage_config.py` 분리 + 최종 정리
        **작업 상세:** `settings/web/flow/target/delays` 의 `*_defaults/load_*/save_*` 를 `core/storage_config.py` 로 이동. storage.py 에는 프리미티브(`DATA_DIR/_ensure_data_dir/_path/_coerce/_kv_defaults/_load_kv/_save_kv/results_path`)와 re-export 만 남긴다. 최종 `wc -l core/storage*.py` 로 각 파일 < 500 확인(storage.py = 117줄).
        - [x] R2.5.T1 `pytest tests/ -v` 전체 통과(140 passed). `cd src && .venv/bin/python -c "import core.storage as s; s.DATA_DIR; s.load_web(); s.load_selectors()"` 스모크.
        - [x] R2.5 커밋: `refactor(storage): split config groups into storage_config.py; storage.py is now a facade`

---

### 적용 규칙 (요약)
- **스토리지 격리:** 파일 I/O 는 여전히 storage 계열에만. sibling 은 DATA_DIR 직접 접근 금지(프리미티브 경유).
- **테스트 격리:** 기존 autouse `tmp_data_dir` 그대로 동작해야 함(핵심 검증 포인트).
- 커밋 메시지 끝에 `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.
