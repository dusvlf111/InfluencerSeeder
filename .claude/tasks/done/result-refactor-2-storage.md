# 결과보고서: tasks-refactor-2-storage.md

> 완료일: 2026-06-10
> 범위: `core/storage.py`(508줄) 관심사 분리 — DATA_DIR monkeypatch 계약 보존

## 구현 요약
| 작업 | 상태 | 커밋 |
|------|------|------|
| R2.1 defaults 데이터 추출 + `_path` 프리미티브 | ✅ | `4a12ea7` |
| R2.2 state.json 분리 (storage_state.py) | ✅ | `1e2e386` |
| R2.3 results/excluded 분리 (storage_results.py) | ✅ | `4c39c5e` |
| R2.4 selectors 분리 (storage_selectors.py) | ✅ | `1fc90ce` |
| R2.5 config 그룹 분리 (storage_config.py) + 파사드화 | ✅ | `2a92455` |

## 파일 구조 (줄 수, 전부 <500)
- `core/storage.py` **508 → 117** (파사드: DATA_DIR + 프리미티브 + 전체 re-export)
- `core/storage_defaults.py` 157 (순수 데이터) · `storage_config.py` 142 · `storage_results.py` 111 · `storage_selectors.py` 64 · `storage_state.py` 36

## 테스트 결과
- `pytest tests/ -v` → **140 passed**. 매 커밋 전체 통과.

## 핵심 계약 보존
- `core/storage.py` 모듈(파사드) 유지. `DATA_DIR` + 경로 프리미티브(`_path/_load_kv/_save_kv/_ensure_data_dir/_coerce/results_path`)는 storage.py 에만.
- sibling 4개는 DATA_DIR 직접 참조 0 — 전부 `from core import storage as _st` 후 `_st._path(...)` 경유 → `monkeypatch.setattr(storage,"DATA_DIR",tmp_path)` 가 분리 함수에도 적용.
- 공개 이름 30개 전부 `core.storage` re-export. `patch("core.storage.save_state")` 동작.

## 이슈
- `results_path` 는 경로 프리미티브라 storage.py 잔류(sibling 은 `_st.results_path()` 경유) — task R2.3 본문보다 "절대 원칙" 우선.
- 분리 후 미사용 `json`/`shutil` import 정리.
