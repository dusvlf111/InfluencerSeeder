# 결과보고서: tasks-prd-260610-3-push1.md

> 완료일: 2026-06-10
> Push 범위: `core/storage.py` 5분리(web/selectors·priority/delays/flow/target) + results 프로필 스키마·dedup + state.json 재개 상태

## 구현 요약

| 작업 | 상태 | 커밋 |
|------|------|------|
| 1.1 web.csv (load_web/save_web/web_defaults) | ✅ | `301f529` |
| 1.2 selectors.csv priority fallback 체인 + 정렬 load | ✅ | `ca2b11b` |
| 1.3 delays.csv (load_delays→tuple map/save_delays) | ✅ | `bafc3dd` |
| 1.4 flow.csv (load_flow/save_flow) | ✅ | `8bb07e2` |
| 1.5 target.csv (load_target/save_target) | ✅ | `e2f1563` |
| 1.6 results 프로필 스키마 + dedup append + seen_usernames | ✅ | `6940558` |
| 1.7 state.json (load/save/clear_state) | ✅ | `e059f18` |
| 1.8 전체 회귀 + stale 테스트 정리 | ✅ | `7169686` |

## 생성/수정 파일
- `src/core/storage.py` — web/flow/target/delays 5분리 함수군, `seen_usernames()`, state.json 3함수, `load_selectors` priority 정렬, `append_result -> bool` dedup, `_RESULTS_FIELDNAMES` 프로필 스키마 교체. 내부 헬퍼 `_kv_defaults/_load_kv/_save_kv/_normalize_selector_row` 추가. v2 함수(`load_settings` 등) 호환 유지.
- `src/tests/test_storage.py` — 클래스 9종(TestSettings/Excluded/Web/Selectors/Delays/Flow/Target/ResultsDedup/State), autouse `tmp_data_dir` fixture.

## 테스트 결과
- `cd src && .venv/bin/pytest tests/ -v` → **83 passed** (storage 53, scraper_utils 24, sheets 6). 실패/에러 0.

## 이슈 및 특이사항
- **stale 테스트 정리:** 기존 `TestSettings`(없는 키 `max_scroll`/`sel_tab_recent`/`settings.json` 참조), `TestExcluded`(`excluded.json` 참조)를 현행 CSV 스키마(`settings.csv`/`excluded.csv`)에 맞게 교체. 사유는 `7169686` 커밋 메시지에 기록.
- **호환성 확인:** `scraper.py` 의 `append_result` 호출부는 반환값 미사용 → bool 추가 안전. `load_selectors` 소비부는 `step_id` 만 사용 → priority 추가 무해(Push2에서 priority 순회 구현).
- **bool 표기:** web/flow CSV의 bool 값은 문자열(`"true"/"false"`)로 로드 → 소비측에서 `str(v).lower()=="true"` 해석 필요.
- git 원격 미설정 → push 생략 (로컬 커밋만).

## 다음 Push 인계 (storage 시그니처 확정본)
```
load_web/save_web/web_defaults · load_flow/save_flow/flow_defaults · load_target/save_target/target_defaults
load_delays() -> dict[str,(min,max)] / save_delays / delay_defaults
load_selectors() -> list[dict]{step_id,step_name,priority:int,selector_type,selector_value} (step_id별 priority asc)
append_result(info) -> bool (True=신규저장, False=중복/빈) · seen_usernames() -> set[str](lower)
load_state()->dict|None · save_state(dict) · clear_state()
```
