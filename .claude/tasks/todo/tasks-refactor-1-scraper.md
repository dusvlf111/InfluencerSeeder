# Tasks: Refactor 1 — scraper.py 모듈화 + Flow 추상화

> 목적: `core/scraper.py`(917줄, 단일 모놀리식)를 **역량(capability) / 드라이버 / 파싱 / 플로우(flow)** 로 분리하고,
> **새 수집 플로우를 유연하게 추가**할 수 있도록 Step/Flow 추상화 + 레지스트리를 도입한다.
> 상태: 🔲 진행 중
> 선행: Push1·2 완료(현재 상태). 후행: Push3·4 는 이 리팩터 이후 진행(공개 API 불변이라 영향 없음).

---

### 실행 환경
- **사용 가능 도구:** Read, Write, Edit, Bash, Glob, Grep
- **사용 불가 도구:** Skill, Agent
- **테스트:** `cd src && .venv/bin/pytest tests/ -v` (매 커밋마다 **전체** 실행 — 124개가 계속 통과해야 함)
- **병렬 작업:** 불가

### 참조 문서 (작업 전 반드시 Read)
| 문서 | 용도 |
|------|------|
| `src/core/scraper.py` | 분리 대상 원본 (917줄) |
| `src/tests/test_scraper_utils.py` | **patch 계약의 원천** — 깨지면 안 되는 124개 중 65개 |
| `src/CLAUDE.md` | 신호/슬롯·스토리지 격리·테스트 격리 규칙 |
| `src/ui/panels/control_panel.py` | `ScraperThread(**params)` 호출부 (공개 생성자 시그니처 소비자) |

---

### ⚠️ 절대 깨면 안 되는 monkeypatch / import 계약

테스트가 다음을 가정한다. **리팩터 후에도 그대로 성립해야 한다:**

1. `from core.scraper import parse_followers, ScraperThread, _build_chrome_options, _apply_stealth, _UA_POOL`
   → 이 이름들이 `core.scraper` 에서 **import 가능**해야 함(분리해도 re-export).
2. `patch("core.scraper.get_follower_count", return_value=...)` 가 `_passes_follower_filter` 에 영향.
   → **`ScraperThread` 클래스와 `_passes_follower_filter` 메서드는 `core/scraper.py`(모듈) 안에 정의**되어야 하고,
     `get_follower_count` 는 `core/scraper.py` 네임스페이스로 **import** 되어야 한다(메서드의 `__globals__` 가 `core.scraper` 여야 patch 가 닿음).
3. `patch("core.scraper.random.choice")`, `patch("core.scraper.time.sleep")`, `patch("core.scraper.random.uniform")`
   → `core/scraper.py` 가 `import time`, `import random` 을 유지(싱글톤이라 어느 모듈에서 호출해도 patch 적용됨).
4. **`core/scraper.py` 는 `.py` 모듈로 유지한다. 절대 `core/scraper/` 패키지로 바꾸지 말 것.**
   (패키지로 바꾸면 위 2번 `__globals__` 계약이 깨진다.)
5. `ScraperThread.__new__(ScraperThread)` 로 생성 후 속성만 세팅해 호출하는 단위 테스트가 많다.
   → 다음 메서드는 **반드시 `ScraperThread` 에 그대로 유지**(시그니처·동작 불변):
   `_resolve_selector(driver, step_id)`, `_build_selector_chains(rows)`(staticmethod), `_get_by(step_id)`,
   `_human_type(el, text)`, `_typing_delay_range()`, `_should_skip(username)`, `_norm_username(u)`(staticmethod),
   `_is_blocked(driver)`, `_save_state(tag_index, post_index)`, `_passes_follower_filter(driver, username)`,
   `_valid`/`_is_valid_username`(staticmethod), `_random_delay(step_key)`, `_log`, `_step`.
   생성자(`__init__`) 시그니처·동작도 불변(TestResumeAndState 6개가 검증).

> 위반 여부는 **매 커밋 후 `pytest tests/ -v` 전체 실행**으로 확인. 빨강이면 다음 단계로 넘어가지 말 것.

---

## 목표 아키텍처

```
core/
  scraper.py            # ScraperThread(QThread): 신호 + __init__ + "역량" 메서드(위 5번 목록) + run()
                        #   run() 은 core.flows.get_flow(mode) 로 Flow 를 받아 위임.
                        #   re-export: parse_followers, get_follower_count, init_driver,
                        #     _build_chrome_options, _apply_stealth, _UA_POOL, _WINDOW_PRESETS,
                        #     _BLACKLISTED_PATHS, _truthy
  scraper_driver.py     # _truthy, _UA_POOL, _WINDOW_PRESETS, _build_chrome_options, _apply_stealth, init_driver
  scraper_parsing.py    # _BLACKLISTED_PATHS, parse_followers, get_follower_count
  flows/
    __init__.py         # 레지스트리: register(mode, cls) / get_flow(mode) -> Flow ; 기본 등록 hashtag(+keyword 별칭)
    base.py             # Outcome(enum), Step(ABC: execute(ctx)->Outcome), Flow(ABC: mode, run(ctx))
    context.py          # ScrapeContext(dataclass): thread, driver, keyword, tag_grid_url, +상태
    steps.py            # 재사용 Step들 (아래) — ctx.thread 의 역량 메서드를 호출
    hashtag.py          # HashtagFlow(Flow): 태그/게시물 중첩 루프를 steps 로 조립
```

**핵심:** 역량(저수준, 테스트됨)은 `ScraperThread` 에 남고, 오케스트레이션(플로우 정책)은 `flows/` 로 빠져
`mode` 별로 교체 가능. **새 플로우 추가 = `Flow` 서브클래스 작성 + `register()`** 한 줄.

---

## 작업

- [ ] R1.0 scraper 모듈화 + Flow 추상화 (전 범위)

    - [x] R1.1 `scraper_parsing.py` 추출
        **작업 상세:** `_BLACKLISTED_PATHS`, `parse_followers`, `get_follower_count` 를 `core/scraper_parsing.py` 로 이동.
        `core/scraper.py` 상단에서 `from core.scraper_parsing import parse_followers, get_follower_count, _BLACKLISTED_PATHS` 로 re-export.
        ⚠️ `get_follower_count` 가 `core.scraper` 네임스페이스에 존재해야 함(계약 2). `_passes_follower_filter` 는 `core/scraper.py` 에 그대로 둠.
        - [x] R1.1.T1 `cd src && .venv/bin/pytest tests/ -v` → **124 passed** 확인 (특히 `TestParseFollowers`, `TestScraperThreadPassesFollowerFilter`).
        - [x] R1.1 커밋: `refactor(scraper): extract parsing helpers to scraper_parsing.py`

    - [x] R1.2 `scraper_driver.py` 추출
        **작업 상세:** `_truthy, _UA_POOL, _WINDOW_PRESETS, _build_chrome_options, _apply_stealth, init_driver` 를 `core/scraper_driver.py` 로 이동.
        `core/scraper.py` 에서 `from core.scraper_driver import (init_driver, _build_chrome_options, _apply_stealth, _UA_POOL, _WINDOW_PRESETS, _truthy)` re-export.
        ⚠️ `scraper_driver.py` 는 `import random` 유지(계약 3, 싱글톤). `init_driver` 의 `from core.storage import load_web` 지연 import 유지.
        - [x] R1.2.T1 `pytest tests/ -v` → 124 passed (특히 `TestStealth` 10개, import 라인).
        - [x] R1.2 커밋: `refactor(scraper): extract driver/stealth to scraper_driver.py`

    - [x] R1.3 `flows/` 추상화 골격 (base + context + 레지스트리)
        **작업 상세:**
        `core/flows/base.py`:
        ```python
        from abc import ABC, abstractmethod
        from enum import Enum, auto
        class Outcome(Enum):
            CONTINUE = auto()   # 다음 step
            SKIP_POST = auto()  # 현재 게시물 건너뜀
            NEXT_TAG = auto()   # 현재 태그 루프 종료
            BLOCKED = auto()    # 차단 — 전체 중단
            STOP = auto()       # 사용자 중단/목표 달성
        class Step(ABC):
            @abstractmethod
            def execute(self, ctx) -> "Outcome": ...
        class Flow(ABC):
            mode: str = "base"
            @abstractmethod
            def run(self, ctx) -> None: ...
        ```
        `core/flows/context.py`: `@dataclass` `ScrapeContext` — `thread`, `driver`, `keyword: str = ""`, `tag_grid_url: str = ""`, `post_urls: list = field(default_factory=list)`. 편의 프로퍼티 `collected`(→`thread._collected`) 등은 thread 위임.
        `core/flows/__init__.py`: `_REGISTRY: dict[str, type] = {}`; `register(mode, cls)`; `get_flow(mode) -> Flow`(미등록 mode 는 기본 `"hashtag"` 로 폴백 + 로그). 모듈 하단에서 `from core.flows.hashtag import HashtagFlow; register("hashtag", HashtagFlow); register("keyword", HashtagFlow)`.
        - [x] R1.3.T1 `tests/test_flows.py` 신규 (`class TestFlowRegistry`): `get_flow("hashtag")` 가 `HashtagFlow` 인스턴스, 미등록 mode 폴백, `Step`/`Flow` 추상 인스턴스화 시 `TypeError`.
        - [x] R1.3.T2 `pytest tests/test_flows.py -v` + 전체 `pytest tests/ -v` 통과.
        - [x] R1.3 커밋: `feat(flows): add Step/Flow abstraction + registry`

    - [ ] R1.4 재사용 Step 구현 (`flows/steps.py`)
        **작업 상세:** 현재 `_step1..6`/`_peek_username_from_post`/`_click_coord` 로직을 Step 클래스로 이전. 각 Step 은 `ctx.thread` 의 **역량 메서드**(`_resolve_selector`, `_get_by`, `_human_type`, `_should_skip`, `_random_delay`, `_is_blocked`, `_step`, `_log`)와 `ctx.driver` 만 사용. 파일 I/O 는 `core.storage`(append_result 등) 경유.
        구현 Step(예시 명): `OpenHomeIfNeeded`, `ClickSearchIcon`, `TypeSearch`, `ClickTagSuggestion`, `CollectPostUrls`, `PeekUsernameGate`(조기 dedup §6 — Outcome.SKIP_POST), `NavigateToProfile`, `ExtractProfile`, `ApplyFilters`(target.csv 필터, 탈락 시 seen 추가 + SKIP_POST), `SaveResult`(append_result dedup, result_signal, progress_signal, _save_state).
        `_click_coord` 는 thread 에 남겨도 되고 steps 의 헬퍼로 옮겨도 됨(테스트 없음). 좌표 폴백(`("coord",(x,y))`) 처리 유지.
        ⚠️ 기존 run() 의 **동작(로그 prefix `[1]`~`[6]`/`[skip]`/`[OK]`/`[grid]`, 신호 emit 순서, dedup/필터/저장 로직, source_tag/source_post_url 기록, collected 증가, _save_state(tag,post+1))을 그대로 보존**.
        - [ ] R1.4.T1 `pytest tests/ -v` → 124 passed (run() 아직 미전환이면 step 클래스만 추가된 상태로 통과).
        - [ ] R1.4 커밋: `feat(flows): reusable Step implementations for the 6-step pipeline`

    - [ ] R1.5 `HashtagFlow` 구현 + `run()` 위임 전환
        **작업 상세:** `core/flows/hashtag.py` 에 `class HashtagFlow(Flow)`: `mode="hashtag"`. `run(ctx)` 가 현재 `core/scraper.py:run()` 의 **태그 루프 + 게시물 루프**(resume 인덱스, 조기 skip 게이트, 차단 감지, step별 save_state, dedup/필터/저장)를 steps 로 조립해 수행.
        `core/scraper.py:run()` 은 **인프라만 유지**: 브라우저 기동(`init_driver(self._web)`), 로그인 대기 루프, `self._seen` 통합 구성(results∪excluded∪resume), 최초 `_is_blocked` 체크, `flow = get_flow(self.mode); flow.run(ScrapeContext(thread=self, driver=driver))`, 정상 완료 시 `storage.clear_state()`, `finally` 에서 `driver.quit()` + `done_signal`. 예외 시 `error_signal`.
        `self.mode` 가 `"keyword"` 여도 현재는 HashtagFlow 로 동작(별칭 등록).
        - [ ] R1.5.T1 `tests/test_flows.py` 에 `class TestHashtagFlowSmoke` 추가: 완전 Mock 한 `ScraperThread`(또는 `__new__` + 필요한 역량 메서드를 MagicMock/실제 혼합)와 MagicMock driver 로 `HashtagFlow().run(ctx)` 호출 시 — 게시물 0개면 즉시 정상 종료, 1개 정상 프로필이면 `append_result`(patch)·`result_signal`(MagicMock) 호출됨, dedup 대상이면 skip. (네트워크 없이 Mock 만.)
        - [ ] R1.5.T2 `pytest tests/ -v` 전체 통과(124 + 신규 flow 테스트). 실패 시 원인 수정.
        - [ ] R1.5 커밋: `refactor(scraper): delegate run() to pluggable HashtagFlow`

    - [ ] R1.6 정리 + 문서화
        **작업 상세:** `core/scraper.py` 에 남은 죽은 코드(이전된 `_step*` 잔재 등) 제거. 최종 `wc -l core/scraper.py core/scraper_driver.py core/scraper_parsing.py core/flows/*.py` 로 길이 확인(scraper.py 목표 ≤ ~450줄). `src/CLAUDE.md` 의 "디렉토리 구조"·"진행 중 작업" 절에 flows/ 추상화와 "새 플로우 추가법(= Flow 서브클래스 + register)"을 2~4줄 추가.
        - [ ] R1.6.T1 `pytest tests/ -v` 최종 전체 통과. `cd src && .venv/bin/python -c "import core.scraper, core.flows"` 임포트 스모크.
        - [ ] R1.6 커밋: `docs+refactor(scraper): cleanup + document flow extension point`

---

### 적용 규칙 (요약)
- **신호/슬롯:** Step/Flow 도 UI 직접 조작 금지. `ctx.thread.<signal>.emit(...)` 만. 기존 신호 시그니처 불변.
- **스토리지 경유:** 파일 I/O 는 `core.storage` 함수만(직접 open 금지).
- **테스트 격리:** 새 flow 테스트도 MagicMock driver/thread + `core.storage` patch. 실제 인스타/브라우저 호출 금지.
- 커밋 메시지 끝에 `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>` 추가.
