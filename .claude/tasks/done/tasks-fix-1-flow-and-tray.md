# Tasks: Fix 1 — 멀티키워드 순차검색 + 프로필 추출 폴백 + 트레이 복귀

> 사용자 리포트(3건): ① 여러 태그(쉼표) 입력 시 각 키워드를 개별 검색해 순차 수집해야 함, ② 프로필 정보 수집 실패, ③ 트레이(백그라운드)에서 복귀 시 실행 중 화면이 안 보이고 잘못된 크기로 새로 뜸.
> 상태: ✅ 완료 (A/B/C/D — 263 passed)
> 선행: 없음(현재 244 passed). 매 커밋 전체 green 유지.

---

### 실행 환경
- **사용 가능 도구:** Read, Write, Edit, Bash, Glob, Grep
- **사용 불가:** Skill, Agent
- **테스트:** `cd src && .venv/bin/pytest tests/ -v` (매 커밋 전체 — 현재 244)
- ⚠️ 실제 인스타/브라우저 호출 금지(MagicMock + storage patch). 라이브 동작은 사용자가 `python main.py` 로 검증.
- git staging 은 **본인 파일만**(`git add <경로>`). `git add -A` 금지(무관 파일 run_*.command/bat/README 존재).
- 커밋 메시지 끝: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`

### 참조 문서 (작업 전 Read)
| 문서 | 용도 |
|------|------|
| `src/core/flows/configurable.py` | **실제 실행되는 기본 flow**(`hashtag` 등록). run/_run_per_tag/_run_per_post |
| `src/core/flows/hashtag.py` | `hashtag_legacy` 폴백 flow — 동일하게 수정해 일관성 유지 |
| `src/core/flows/steps.py` | TypeStep/ClickIndexStep/ExtractProfile/_expand_param 등 |
| `src/core/scraper.py` | `_save_state`, 생성자 resume 파싱(`_start_tag_index` 등), `_get_by`/`_resolve_selector` |
| `src/ui/main_window.py` | 트레이 `_restore_from_tray`/`changeEvent`/`closeEvent` |
| `src/core/storage_defaults.py` | selectors 기본값(`username_text`/`followers_count`/`following_count`/`posts_count`/`bio_text`/`website_link` step_id) |
| `src/tests/test_flows.py` | flow 스모크/동치 테스트(수정 필요) |
| `src/CLAUDE.md` | 신호/슬롯·스토리지·테스트 격리 규칙 |

### ⚠️ 계약
- 기존 신호 시그니처 불변. `core/scraper.py`·`core/storage.py` 모듈 유지. Step/Flow 는 UI 직접 조작 금지.
- 파일 I/O 는 `core.storage` 만. 디자인 토큰(hex 직접 금지).

---

## A. 멀티키워드 순차검색 (핵심)

**현재:** `keyword = t.search_term.lstrip("#")` 하나를 `#{keyword}` 로 타이핑하고 `for tag_index in range(_start_tag_index, max_tags)` 로 **추천태그를 순환**. → `취준생,개발자` 가 `#취준생,개발자` 한 번으로 검색됨.

**원하는 동작(사용자 확정):** **각 키워드 = 해당 태그 1개.** 쉼표/줄바꿈으로 키워드를 분리해 **키워드마다: 검색 → 첫 추천태그(index 0) 클릭 → 게시물 수집·처리 → 다음 키워드**. 단일 키워드면 그 태그 1개만(추천태그 순환 안 함).

### A.1 키워드 파서 + 플랜 헬퍼 (`core/flows/steps.py` 상단 근처)
```python
import re as _re  # 이미 re import 있으면 재사용
def parse_keywords(search_term):
    """'인턴, 취준생\n개발자' → ['인턴','취준생','개발자'] (쉼표/줄바꿈 분리, # 제거, 중복제거 순서유지)."""
    out, seen = [], set()
    for raw in re.split(r"[,\n]", search_term or ""):
        k = raw.strip().lstrip("#").strip()
        if k and k.lower() not in seen:
            seen.add(k.lower()); out.append(k)
    return out or [""]

def keyword_tag_plan(search_term, max_tags=1):
    """[(keyword, suggestion_index)] — 키워드당 첫 추천태그 1개."""
    return [(kw, 0) for kw in parse_keywords(search_term)]
```
- T1 단위 테스트: 쉼표/줄바꿈/공백/#/중복/빈문자 케이스.

### A.2 `ConfigurableFlow.run` 멀티키워드 루프
- `plan = keyword_tag_plan(t.search_term, t.max_tags)` (import 추가).
- 기존 `for tag_index in range(t._start_tag_index, t.max_tags)` 를 **`for plan_idx in range(t._start_tag_index, len(plan))`** 로 교체.
- ⚠️ **`max_tags` 는 더 이상 루프 상한이 아님** — 처리할 태그 수 = 입력한 쉼표 키워드 수(전부 처리). `max_tags` 설정은 하위호환을 위해 남기되 루프를 제한하지 않는다. 전체 수집량은 `count`(수집 수)가 제한.
- 키워드당 수집 게시물 수는 기존 `t.posts_per_tag`(= `CollectPostUrls` target) 가 그대로 적용 → "태그(키워드)당 게시물 수"가 됨. **이 동작 보존**(추가 작업 없음, 단 라벨은 D 에서 정리).
- 루프 안:
  ```python
  keyword, sugg_idx = plan[plan_idx]
  ctx.keyword = keyword
  ctx.tag_index = sugg_idx        # 클릭할 추천태그 index (멀티키워드면 0)
  t._current_plan_index = plan_idx
  ```
- `_run_per_tag`/`_run_per_post` 에 넘기는 "tag 루프 커서"는 **plan_idx** 로 통일(상태저장·resume 비교·상태메시지용). 단 **ClickIndexStep 이 클릭하는 추천태그 index 는 `ctx.tag_index`(=sugg_idx)** 이어야 함 — 둘을 분리할 것.
  - `_run_per_tag(ctx, per_tag, per_post, plan_idx, n_total)`: blocked 시 `t._save_state(plan_idx, 0)`. 상태메시지의 `(tag X/Y)` 는 `(키워드 {plan_idx+1}/{len(plan)})` 로 바꿔도 됨.
  - Step3 상태메시지: `f"Step {step_no}/{n_total} — '{keyword}' 검색·태그 선택"` 처럼 keyword 표기.
  - `_run_per_post(ctx, per_post, plan_idx, n_total)`: `resume_post_start` 비교를 `plan_idx == t._start_tag_index` 로(그대로). `_save_state` 호출은 plan_idx 사용.
- `SaveResult` 의 `_save_state(tag, post+1)` 는 Step 내부에서 `ctx.tag_index` 를 쓰면 안 됨 → **plan 커서**를 써야 함. `ctx.plan_index`(또는 `t._current_plan_index`)를 사용하도록 `SaveResult`/`_save_state` 호출 지점을 맞출 것(아래 A.4).

### A.3 `HashtagFlow.run` 동일 적용
- 동일하게 `plan` 루프로 교체(legacy 일관성). 동치 단순하므로 같은 패턴.

### A.4 `_save_state` 가 키워드/플랜 인덱스를 보존 (`core/scraper.py`)
- `_save_state(self, tag_index, post_index)` 의 payload 에 `"keyword_index": int(getattr(self, "_current_plan_index", tag_index))` 추가(기존 키 유지 — `tag_index` 도 그대로 둠; 둘이 같아도 무방).
- 생성자 resume 파싱에 `self._start_tag_index = int(resume_state.get("tag_index", ...))` 는 유지(플랜 커서로 재사용). `keyword_index` 가 있으면 그것을 우선:
  `self._start_tag_index = int(resume_state.get("keyword_index", resume_state.get("tag_index", self.tag_start_index)))`.
- `self._current_plan_index` 를 `__init__` 에서 `self._start_tag_index` 로 초기화.
- ⚠️ 기존 `TestResumeAndState` 6개 통과 유지(키 추가는 additive). `test_save_state_calls_storage` 는 `tag_index/post_index/collected_count/seen_usernames/keyword/updated_at` 만 단언하므로 keyword_index 추가는 안전. 필요하면 keyword_index 단언 추가.

### A.5 테스트 갱신 (`tests/test_flows.py`)
- **동치 의미 변경:** 단일 키워드는 이제 **추천태그 1개**(index 0)만 — 기존 "max_tags 만큼 순환" 가정 테스트는 신규 의미로 수정.
- 멀티키워드 신규 테스트: search_term `"인턴,취준생"` + MagicMock 으로 ClickIndexStep/CollectPostUrls/Extract seam patch → 키워드 2개가 각각 검색되어 `ctx.keyword` 가 순서대로 `인턴`,`취준생` 으로 바뀌고 각 키워드의 post 가 처리됨을 검증.
- `parse_keywords`/`keyword_tag_plan` 단위 테스트(A.1.T1).
- **커밋:** `feat(flows): per-keyword sequential search (comma/newline keywords = one tag each)`

---

## B. 프로필 추출 폴백 — 설정 셀렉터 사용 (`core/flows/steps.py` `ExtractProfile`)

**현재:** meta description + page_source 정규식 + 하드코딩 bio CSS 만 사용 → 인스타 DOM 변경 시 비어옴.

**수정:** 기존 방식으로 못 채운 필드를, 사용자가 버튼매핑 탭에서 설정한 셀렉터(`selectors.csv`)로 폴백 추출:
- `username_text` → `full_name`(또는 표시명) 보조
- `followers_count` → `followers` (텍스트 → 그대로 저장; 숫자 변환은 기존 parse_followers 활용처에서)
- `following_count` → `following`
- `posts_count` → `posts_count`
- `bio_text` → `bio`
- `website_link` → `website` (`el.get_attribute("href") or el.text`)
- 구현: 각 필드가 비었을 때만 `t._resolve_selector(driver, step_id)` 로 요소를 찾아 `.text`/`title`/`href` 추출. `_resolve_selector` 는 priority 폴백 체인을 사용(설정 우선). 실패/없음은 조용히 무시(기존 값 유지). 로그는 기존 `[6]` 한 줄 유지하되 어떤 소스(meta/selector)에서 왔는지 디버그 로그 추가 가능.
- ⚠️ username 자체는 URL 기반 유지(기존). 셀렉터 폴백은 **보강만**, 기존 동작/로그 prefix 보존.
- T: `ExtractProfile` 가 meta 로 못 채운 followers 를 `followers_count` 셀렉터(MagicMock `_resolve_selector` 반환 요소)로 채우는 테스트. 기존 추출 테스트 회귀 없음.
- **커밋:** `fix(flows): ExtractProfile falls back to user-configured selectors for empty fields`

---

## C. 트레이 복귀 버그 (`src/ui/main_window.py`)

**현재:** `_restore_from_tray` 가 `showNormal()/activateWindow()/raise_()` 만 → 최소화상태/geometry 가 깨져 "세로(잘못된 크기)"로 뜨고 실행 중 화면이 제대로 안 보임.

**수정:**
- `changeEvent`/`closeEvent` 에서 `hide()` **직전에 geometry 저장**: `self._saved_geometry = self.saveGeometry()`.
- `_restore_from_tray`:
  ```python
  def _restore_from_tray(self):
      self.setWindowState(self.windowState() & ~Qt.WindowState.WindowMinimized)
      if getattr(self, "_saved_geometry", None):
          self.restoreGeometry(self._saved_geometry)
      self.showNormal()
      self.show()
      self.raise_()
      self.activateWindow()
  ```
- 복귀 시 **수집 진행 화면 유지**: 스택을 메인(index 0)으로 두되 `_results` 상태(진행/로그/결과)는 그대로(같은 위젯이라 보존됨). 설정 페이지에 있었다면 메인으로 전환하지 말 것(현재 페이지 유지) — 단, 최소화가 메인에서 일어났다면 그대로 메인.
- T(`tests/test_main_window.py` TestTray): geometry 저장/복원 경로가 예외 없이 동작(offscreen), `_restore_from_tray` 호출 후 `isMinimized()` False, 트레이 미지원 환경 안전.
- **커밋:** `fix(ui): restore tray window with saved geometry and cleared minimized state`

---

## D. 플로우 설정 라벨 명확화 (`src/ui/settings/flow_tab.py`)

사용자 요청: "태그 안에 게시물 몇 개 클릭하고 넘어갈지 세팅" — 이미 `posts_per_tag` 로 존재하나 라벨이 영어/모호. 멀티키워드 변경에 맞춰 한국어로 정리:
- `posts_per_tag` 행 라벨 → **"태그(키워드)당 게시물 수"**, 툴팁 → "키워드 1개당 수집할 게시물 수. 이만큼 모으면 다음 키워드로 넘어감".
- `max_tags` 행 라벨 → **"최대 태그 수(레거시)"**, 툴팁 → "쉼표로 키워드를 여러 개 입력하면 각 키워드가 하나의 태그로 검색됩니다. 이 값은 키워드 검색 방식에선 사용되지 않습니다(하위호환 유지)".
- 나머지 행도 한국어로(선택): `tag_start_index`→"시작 태그 인덱스", `scroll_max_attempts`→"그리드 최대 스크롤", `skip_visited_profile`→"방문한 프로필 건너뛰기", `stop_on_consecutive_miss`→"연속 미수집 시 중단".
- ⚠️ 위젯 속성명(`_fl_posts_per_tag` 등)·저장 키(`posts_per_tag` 등)·`storage` 스키마는 **변경 금지**(라벨/툴팁 텍스트만). 기존 `tests/test_settings_view.py` 통과 유지.
- **커밋:** `feat(settings): clearer Korean flow-tab labels (posts-per-keyword)`

---

## 완료 보고
- A/B/C 각 구현 요약 + 커밋 해시
- `parse_keywords`/`keyword_tag_plan` 동작, 멀티키워드 루프 구조(plan_idx vs suggestion index 분리), resume 처리
- ExtractProfile 폴백 필드/셀렉터 매핑
- 트레이 복귀 수정 내용
- 최종 `pytest tests/ -v` 통과 개수
- 사용자가 라이브로 확인해야 할 항목(프로필 셀렉터는 버튼매핑 탭에서 설정 후 검증)
