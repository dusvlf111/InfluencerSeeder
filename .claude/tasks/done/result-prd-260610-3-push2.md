# 결과보고서: tasks-prd-260610-3-push2.md

> 완료일: 2026-06-10
> Push 범위: `core/scraper.py` ScraperThread — priority 셀렉터 폴백, stealth 핑거프린트, 사람같은 타이핑, 조기 dedup skip, state 재개, 차단 감지, 신규 신호

## 구현 요약

| 작업 | 상태 | 커밋 |
|------|------|------|
| 2.1 priority 셀렉터 폴백 체인 `_resolve_selector` | ✅ | `99ab6fe` |
| 2.2 stealth/UA/창크기/headless `_apply_stealth`·`init_driver(web)` | ✅ | `dce0d05` |
| 2.2.T3 window_width=0 폴백 버그 수정 | ✅ | `dce0d05` |
| 2.3 `_human_type` 글자별 타이핑 | ✅ | `897b8a9` |
| 2.4 조기 dedup 게이트 `_should_skip` + skip/blocked 신호 | ✅ | `238c5c1` |
| 2.5 생성자 재편 + resume + step별 save_state | ✅ | `74b11b5` |
| 2.6 차단 감지 `_is_blocked` + 일시정지 | ✅ | `f06d6d7` |
| 2.7 전체 회귀 (124 passed) | ✅ | `7212dfd` |

## 생성/수정 파일
- `src/core/scraper.py` — UA 풀/창 프리셋 상수, `_truthy`/`_build_chrome_options`/`_apply_stealth`/`init_driver(web)`, `skip_signal`/`blocked_signal`, `_resolve_selector`/`_click_coord`/`_human_type`/`_should_skip`/`_peek_username_from_post`/`_save_state`/`_is_blocked`, run() 전면 재편(resume·조기 skip·차단·dedup).
- `src/tests/test_scraper_utils.py` — 신규 6클래스 41테스트(기존 24 호환).

## 테스트 결과
- `cd src && .venv/bin/pytest tests/ -v` → **124 passed** (scraper_utils 65, storage 53, sheets 6).

## 이슈 및 특이사항
- `window_width=0 or 1280` 단락평가 버그(0이 1280으로 치환) → 빈문자만 기본값 적용하도록 수정(2.2.T3).
- 생성자가 `load_selectors()` 자체 로드 시 실제 `DATA_DIR` 쓰기 부작용 → 테스트에 autouse `DATA_DIR`→tmp_path 격리.

## 다음 Push 인계
**ScraperThread 생성자 최종 시그니처:**
```python
ScraperThread(mode, search_term, count, min_followers, max_followers, excluded_set,
              selectors=None, app_settings=None, *,
              web=None, delays=None, flow=None, target=None, resume_state=None)
```
- 기존 위치 인자(control_panel dict) 무변경 동작. 신규 5개는 키워드 기본값 None, 누락 시 `storage.load_*()` 자체 로드.
- `resume_state` 에 `storage.load_state()` 결과 주입 시 재개.

**신규 신호(UI 배선 필요):** `skip_signal(str)`(중복 skip 카운트), `blocked_signal()`(모달 경고+일시정지).
**노출 속성:** `scroll_max_attempts/tag_start_index/stop_on_consecutive_miss/skip_visited_profile/min_following/max_following/min_posts`. 정상 완료 시 `state.json` 자동 삭제.
