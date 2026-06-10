# 결과보고서: tasks-refactor-1-scraper.md

> 완료일: 2026-06-10
> 범위: `core/scraper.py`(917줄) 모듈화 + Flow/Step 추상화(새 플로우 유연 추가)

## 구현 요약
| 작업 | 상태 | 커밋 |
|------|------|------|
| R1.1 parsing 추출 (scraper_parsing.py) | ✅ | `fd5a183` |
| R1.2 driver/stealth 추출 (scraper_driver.py) | ✅ | `66119ab` |
| R1.3 Step/Flow 추상화 + 레지스트리 (flows/) | ✅ | `1678b9f` |
| R1.4 재사용 Step 10종 (flows/steps.py) | ✅ | `6482ce9` |
| R1.5 HashtagFlow + run() 위임 전환 | ✅ | `edc8faf` |
| R1.6 정리 + 문서화 | ✅ | `b5a5516` |

## 파일 구조 (줄 수)
- `core/scraper.py` **917 → 399** (역량 메서드 + 신호 + run() Flow 위임)
- `core/scraper_driver.py` 125 · `core/scraper_parsing.py` 65
- `core/flows/`: `__init__.py` 56(레지스트리) · `base.py` 39 · `context.py` 42 · `steps.py` 339 · `hashtag.py` 166
- `tests/test_flows.py` 신규 (TestFlowRegistry 8 + TestHashtagFlowSmoke 4)

## 테스트 결과
- `pytest tests/ -v` → **136 passed** (기존 124 + flow 12). 매 커밋 전체 통과.

## 새 플로우 추가법
```python
from core.flows.base import Flow
from core.flows import register
class ReelsFlow(Flow):
    mode = "reels"
    def run(self, ctx): ...   # ctx.thread 역량 + steps 조립
register("reels", ReelsFlow)  # ScraperThread(mode="reels") 로 동작
```

## 이슈 및 특이사항 (patch 계약)
- `core/scraper.py` 를 **모듈로 유지**, `_passes_follower_filter` + `get_follower_count` re-export 로 `patch("core.scraper.get_follower_count")` 계약 보존.
- `time`/`random` import 유지(싱글톤 patch). `core/flows/` 만 신규 패키지.
- block 중단 시 `[done]`/`clear_state` 건너뛰기 동작 보존(`thread._blocked` 플래그로 scraper.run() 이 검사).
- dedup skip(1.0s) vs 필터 탈락(sleep 없음) 타이밍·로그 prefix 보존.
- 죽은 코드(`_step1..6`/`_peek_username_from_post`/`_click_coord`)는 steps.py 로 이전 후 제거, 미사용 `re`/`quote` import 정리.
