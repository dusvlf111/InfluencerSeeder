# 결과보고서: tasks-prd-260610-3-push4.md

> 완료일: 2026-06-10
> Push 범위: 메인윈도우 트레이/이어하기/차단모달 + 영속 로깅 + 진행표시

## 구현 요약
| 작업 | 상태 | 커밋 |
|------|------|------|
| 4.1 RunLogger 영속 로그 + qapp fixture | ✅ | `0b95c76` |
| 4.2~4.5 트레이·이어하기·차단/skip·진행표시 | ✅ | `1e35d24` |
| 4.6 통합 회귀 + 체크 | ✅ | `e440772` |

## 생성/수정 파일
- 신규: `core/run_logger.py`(RunLogger, `DATA_DIR/logs/run-*.log` 동적경로), `tests/test_run_logger.py`(6), `tests/test_main_window.py`(26), `tests/conftest.py`(offscreen qapp fixture).
- 수정: `ui/main_window.py`(트레이/이어하기/차단·skip 핸들러/로깅 배선), `ui/panels/control_panel.py`(`resume_requested` 신호, [이어하기], `collect_params`/`set_resume_available`), `ui/panels/results_panel.py`(진행 라벨, `set_step`/`set_skip_count`, `log_color` 순수 헬퍼).

## 신호 배선
- `skip_signal(str)` → `_on_skip`: skip 카운터 누적 + 라벨 + 로그파일
- `blocked_signal()` → `_on_blocked`: `_scraper.stop()` + `QMessageBox.warning` + 로그
- `step_signal/log_signal/done_signal` → 진행표시·로그파일·종료(close+resume 갱신+트레이 알림)

## 테스트 결과
- `pytest tests/ -v` → **185 passed** (기존 153 + run_logger 6 + main_window 26).

## 이슈 및 특이사항
- **잠복 버그 수정:** `control_panel._on_start` 가 v3에서 `list` 가 된 `selector_defaults()` 에 `.keys()` 호출 → `storage.load_selectors()` list 직접 주입으로 교체.
- 헤드리스라 GUI 육안 확인 불가 → import/위젯/resume 토글/run_logger 라이프사이클 스모크로 대체. 트레이는 미지원 환경에서 `_tray=None` 안전 비활성.

## 다음(설정 UI) 인계
- `ControlPanel.resume_requested` 신규, `collect_params()->dict|None`(검색어 비면 None, selectors=load_selectors list).
- `MainWindow._build_params(params, resume_state)` 가 `web/delays/flow/target` 을 `storage.load_*` 로 주입 → **설정 저장만 하면 다음 수집에 반영**.
- `_refresh_resume()` 가 `storage.load_state() is not None` 으로 [이어하기] 토글(`show_main`/`_on_done` 시 호출).
- 트레이 활성 시 `closeEvent` 는 트레이로 숨김. 완전 종료는 트레이 "종료"(`_force_quit`).
