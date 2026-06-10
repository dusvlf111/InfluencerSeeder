# InfluencerSeeder — 프로젝트 규칙 (src/)

인스타그램 해시태그 기반 인플루언서 프로필 수집기. **PyQt6 GUI + Selenium 스크래퍼 + CSV 스토리지**.
설치형 데스크톱 앱(PyInstaller 패키징). 외부 API 의존 없음 — 모든 설정/데이터는 사람이 편집 가능한 평문 CSV.

## 실행 / 테스트

```bash
cd src
.venv/bin/python main.py                 # 앱 실행
.venv/bin/pytest tests/ -v               # 전체 테스트
.venv/bin/pytest tests/test_storage.py -v   # 단일 모듈
```

- 의존성: `requirements.txt`(PyQt6, selenium, webdriver-manager), `requirements-dev.txt`(pytest, pyinstaller).
- ⚠️ **pytest-qt 미설치.** UI 테스트는 `QApplication` 공유 fixture 로 위젯을 직접 생성하고 순수 로직(collect/populate/parse)을 검증한다. 이벤트 루프·실제 클릭 시뮬레이션은 피한다.

## 디렉토리 구조

```
src/
  main.py                  # 진입점: QApplication + 전역 스타일시트 + MainWindow
  core/
    storage.py             # 모든 파일 I/O (CSV) — DATA_DIR 기준
    scraper.py             # ScraperThread(QThread): 신호 + 역량 메서드 + run() (Flow 위임)
    scraper_driver.py      # Chrome Options/stealth/init_driver (scraper.py 가 re-export)
    scraper_parsing.py     # parse_followers / get_follower_count (scraper.py 가 re-export)
    flows/                 # 수집 플로우 추상화 (Step/Flow + 레지스트리)
      base.py              #   Outcome(enum) · Step(ABC) · Flow(ABC)
      context.py           #   ScrapeContext(dataclass): thread/driver/루프 상태
      steps.py             #   재사용 Step (6-step 파이프라인) — ctx.thread 역량 메서드만 호출
      hashtag.py           #   HashtagFlow: 태그/게시물 루프 조립 (keyword 모드 별칭)
      __init__.py          #   register(mode, cls) / get_flow(mode)
    sheets.py              # (v2 잔재, 비사용)
  ui/
    main_window.py         # MainWindow: 신호 배선·스크래퍼 생명주기
    settings_view.py       # SettingsView: QTabWidget 설정 화면
    panels/                # control_panel(좌), results_panel(우)
    widgets/               # follower_filter, excluded_widget
    dialogs/               # login_dialog, settings_dialog
  design/
    tokens.py              # Colors/Typography/Spacing/Radius — 시각 상수 단일 출처
    stylesheet.py          # 토큰 → 전역 QSS 생성
  tests/                   # pytest (test_storage, test_scraper_utils, ...)
  data/                    # 런타임 CSV 출력 (gitignore)
```

수집 흐름: `ControlPanel.start_requested(dict)` → `MainWindow._start_scrape` → `ScraperThread` 6-step
(검색아이콘 → 검색입력 → 태그선택 → 게시물수집 → 프로필진입 → 데이터추출) → 신호로 UI 갱신.

## 핵심 규칙

### 1. 신호/슬롯 (스레드 안전성)
- `ScraperThread`(QThread)는 **UI 위젯을 직접 조작하지 않는다.** 오직 `pyqtSignal` emit 으로만 통신.
  현존 신호: `log_signal(str)`, `progress_signal(int,int)`, `result_signal(dict)`, `done_signal()`,
  `error_signal(str)`, `waiting_login_signal()`, `step_signal(str)`.
- 신호는 메인스레드 슬롯에 연결해서만 위젯을 갱신한다(배선은 `MainWindow._start_scrape`).
- 기존 신호 시그니처는 변경하지 말 것(소비측 호환). 새 기능은 신호 **추가**로.
- `run()` 예외는 `error_signal` emit 후 `finally` 에서 `driver.quit()` + `done_signal`.

### 2. 스토리지 (파일 I/O 격리)
- **모든 파일 I/O 는 `core/storage.py` 에만.** 위젯/스크래퍼는 storage 함수만 호출.
- 경로는 전부 `DATA_DIR` 기준. `DATA_DIR = Path(__file__).parent / "data"`.
  **이 정의를 바꾸지 말 것** — 테스트가 `monkeypatch.setattr(storage, "DATA_DIR", tmp_path)` 로 덮어쓴다.
  파일 경로를 모듈 상수로 캐시하지 말고 함수 내에서 `DATA_DIR` 를 참조한다.
- CSV 입출력: `encoding="utf-8-sig"`, `newline=""`, `csv.DictReader`/`csv.DictWriter`.
- **파일이 없으면** 첫 load 시 기본값을 기록(save)한 뒤 반환한다(`load_settings`/`load_selectors` 패턴).
- 손상된 파일은 `try/except` 로 감싸 기본값/빈값 반환 — 예외를 절대 전파하지 않는다.
- 문자열→숫자 변환은 `_coerce()` 재사용(int→float→str 순 시도).

### 3. 디자인 토큰 / 스타일
- 색상·여백·반경·타이포는 `design/tokens.py`(`Colors.*`/`Spacing.*`/`Radius.*`/`Typography.*`)만 사용.
  **QSS·코드에 hex 리터럴 직접 작성 금지** (예외: `stylesheet.py` 내 일부 음영색은 토큰 보강용으로만).
- 위젯 스타일은 `setObjectName(...)` 부여 → `design/stylesheet.py` 전역 QSS 가 처리.
  기존 objectName: `btnPrimary`(보라 강조), `btnSuccess`(녹색), `btnDanger`(빨강),
  `labelAccent`(보라 텍스트), `labelMuted`(작은 회색), `settingsHeader`.
  새 스타일 필요 시 의미있는 objectName 추가 후 stylesheet 에 규칙 작성.
- 위젯 레이아웃은 기존 패턴: `QVBoxLayout`/`QFormLayout`/`QGridLayout` + `setContentsMargins`/`setSpacing`.

### 4. 로그 색상 컨벤션 (`results_panel.append_log`)
메시지 prefix 로 색 결정 — 새 로그도 이 prefix 규칙을 따른다:
- `[OK]` → `Colors.green` · `[ERROR]`/`[에러]`/`[오류]` → `Colors.red`
- `[wait]` → `Colors.amber` · `[step]` → `Colors.accent_light` · 그 외 → `Colors.muted2`

### 5. 테스트 (pytest)
- 위치: `tests/test_<모듈명>.py`. 클래스 단위로 묶기(`class TestParseFollowers`). 입력 다양성은 `@pytest.mark.parametrize`.
- 커버리지 우선순위: 정상 경로 → 엣지(빈 입력/None/잘못된 형식) → 예외 경로.
- **외부 의존성 격리:**
  - storage: autouse fixture 로 `monkeypatch.setattr(storage, "DATA_DIR", tmp_path)`.
  - Selenium 드라이버·요소: `unittest.mock.MagicMock()`. `time.sleep`/`random.uniform` 은 patch.
  - `ScraperThread` 는 `__new__(ScraperThread)` 로 `__init__` 우회 후 필요한 속성만 수동 세팅(기존 `_make_thread` 패턴).
  - UI: `QApplication` session fixture
    ```python
    @pytest.fixture(scope="session")
    def qapp():
        from PyQt6.QtWidgets import QApplication
        yield QApplication.instance() or QApplication([])
    ```
- **실제 네트워크/브라우저 호출 절대 금지.**

## 데이터 스키마 (현행)

`storage.py` 기준 현재 파일/스키마:
- `settings.csv` (key,value) — 필터·딜레이·수집량 통합. *(v3 에서 web/delays/flow/target 로 분리 예정)*
- `selectors.csv` (step_id,step_name,selector_type,selector_value) — step별 셀렉터. *(v3: priority 컬럼 추가 예정)*
- `excluded.csv` (username) — 수집 제외 계정.
- `results.csv` (username,followers,following,posts_count,bio,website,post_url,profile_url,collected_at).

> ⚠️ `tests/test_storage.py` 일부 테스트는 현행 `storage.py` 와 키가 불일치(stale)할 수 있다.
> storage 수정 시 해당 테스트를 현행 동작에 맞게 갱신할 것.

## 진행 중 작업 (v3)

`.claude/tasks/prd-260610-3.md` (PRD) + `.claude/tasks/todo/tasks-prd-260610-3-push{1..4}.md` (작업 분해)에
**재개(resume)·stealth·설정 5분리·플로우 최적화·영속 로깅** 증분이 정의되어 있다.
구현 시 위 핵심 규칙(신호/스토리지/토큰/테스트 격리)을 그대로 따른다.

### 새 수집 플로우 추가법 (flows/)

`core/scraper.py:run()` 은 인프라(브라우저 기동·로그인 대기·seen 구성)만 담당하고, 수집 정책은
`core.flows.get_flow(self.mode)` 로 받은 `Flow` 에 위임한다. **새 모드 추가 = `Flow` 서브클래스 + `register()`**:

```python
from core.flows.base import Flow
from core.flows import register

class ReelsFlow(Flow):
    mode = "reels"
    def run(self, ctx):
        ...  # ctx.thread 의 역량 메서드 + steps.py Step 조립, ctx.driver 만 사용

register("reels", ReelsFlow)   # 이제 ScraperThread(mode="reels", ...) 로 동작
```

⚠️ `core/scraper.py` 는 반드시 `.py` 모듈로 유지(패키지 금지 — `_passes_follower_filter` 의 patch 계약).
저수준 "역량" 메서드는 `ScraperThread` 에, 오케스트레이션은 `flows/` 에 둔다. Step/Flow 도 UI 직접 조작 금지(`ctx.thread.<signal>.emit()` 만).
