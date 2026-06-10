# 결과보고서: tasks-260610-4-flow-builder.md

> 완료일: 2026-06-10
> 범위: 데이터 기반 ConfigurableFlow + 버튼매핑 카드(스크린샷+가이드) + 플로우 빌더 탭 + 폴더형 설정 공유

## 구현 요약
| 단계 | 상태 | 커밋 |
|------|------|------|
| P0 이미지 에셋 번들링 (assets.py, build.spec) | ✅ | `5ff30b8` |
| P1 storage flow_steps + FLOW_ACTIONS + 폴더 import/export | ✅ | (P0/사전 구현) |
| P2.1 Step 일반화 (Click/Type/ClickIndex + OpenHome/GoBack/Scroll) | ✅ | `e198c00` |
| P2.2/2.3 ConfigurableFlow + ACTIONS 레지스트리 + registry 교체 | ✅ | `606d9ad` |
| P3 버튼매핑 카드 (스크린샷+XPath 가이드+셀렉터 표) | ✅ | `bbaa646` |
| P4 플로우 빌더 탭 (action/selector_ref 드롭다운, 행 추가/삭제/순서) | ✅ | `bbaa646` |
| P5 폴더형 설정 import/export | ✅ | `bbaa646` |

## 핵심 산출물
- `core/storage_flowsteps.py` (flow_steps_defaults/load/save), `core/storage_share.py` (CONFIG_FILES/export_config_to_dir/import_config_from_dir), `storage_defaults.py` (FLOW_ACTIONS 13종 + 기본 10스텝).
- `core/flows/configurable.py` (ConfigurableFlow + ACTIONS), `core/flows/steps.py` (일반화 Step + OpenHome/GoBack/Scroll). registry: hashtag/keyword→ConfigurableFlow, hashtag_legacy→HashtagFlow.
- `ui/settings_view.py` 버튼매핑 카드(QScrollArea) + 플로우 빌더 탭 + 헤더 import/export. `design/stylesheet.py` 카드 objectName 규칙.
- `core/assets.py` + `src/assets/guide/step{1..6}.png`.

## 테스트 결과
- `pytest tests/ -v` → **242 passed** (P2 +10, P3/P4/P5 +20).

## 동작 동치 보존
- 기본 flow_steps 로 `ConfigurableFlow` 가 `HashtagFlow` 와 동일 신호·로그 prefix(`[1]`~`[6]`/`[skip]`/`[OK]`/`[grid]`)·dedup/필터/저장·`_save_state(tag,post+1)`·blocked 처리·resume. flow_steps 손상/빈 경우 HashtagFlow 폴백.

## 최종 settings 탭 구성
`Web → Delays → Flow → Target → Excluded → 버튼매핑 → 플로우 → Dependencies`

## 이슈
- registry 교체로 기존 `TestFlowRegistry`/`test_existing_selectors_tab_kept` 단언을 신규 계약(ConfigurableFlow, 버튼매핑/플로우 탭)에 맞게 갱신.
- P3/P4/P5 가 동일 파일(settings_view.py) 행 교차 → 1개 논리 커밋(`bbaa646`)으로 통합(메시지에 P3/P4/P5 명시).

## 후속 (자동 발견)
- `settings_view.py` 가 **990줄**로 증가 → 사용자 상시 규칙("500줄 이상 리팩터링")에 따라 **refactor-3(믹스인 분리)** 로 후속 처리.

## 남은 수동검증
- 실제 GUI: 버튼매핑 카드 스크린샷 렌더, 플로우 표 드롭다운/체크박스 정렬, QFileDialog 폴더 선택 UX. (offscreen 위젯/populate/collect/save round-trip 은 검증 완료.)
