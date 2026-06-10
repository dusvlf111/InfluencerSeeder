import time      # noqa: F401 — kept for patch("core.scraper.time.sleep")
import random    # noqa: F401 — kept for patch("core.scraper.random.*")
import datetime

from PyQt6.QtCore import QThread, pyqtSignal

# Re-exported parsing helpers (live in core.scraper_parsing). They are imported
# into this namespace so existing `from core.scraper import parse_followers` and
# `patch("core.scraper.get_follower_count", ...)` contracts keep working.
from core.scraper_parsing import (  # noqa: F401
    parse_followers,
    get_follower_count,
    _BLACKLISTED_PATHS,
)

# Re-exported driver/stealth helpers (live in core.scraper_driver). Imported
# into this namespace so `from core.scraper import _build_chrome_options, ...`
# and the `patch("core.scraper.random.choice", ...)` contract keep working.
from core.scraper_driver import (  # noqa: F401
    init_driver,
    _build_chrome_options,
    _apply_stealth,
    _UA_POOL,
    _WINDOW_PRESETS,
    _truthy,
)

# URL fragments that indicate the session was redirected to a block/challenge.
_BLOCKED_URL_MARKERS = ("/accounts/login", "/challenge", "/accounts/suspended")


def _clean_selector_value(value) -> str:
    """Defensive selector_value sanitizer (strip + remove \\r\\n\\t).

    storage 가 이미 정규화하지만, 옛 selectors.csv 데이터나 외부에서 주입된 행을
    대비해 사용 직전 한 번 더 줄바꿈/탭을 제거한다(내부 스페이스는 보존).
    chromedriver 의 ``invalid selector ... SyntaxError`` 를 막는 이중 안전.
    """
    if value is None:
        return ""
    text = str(value).strip()
    for ws in ("\r", "\n", "\t"):
        text = text.replace(ws, "")
    return text


# ── ScraperThread ─────────────────────────────────────────────────────────────

class ScraperThread(QThread):
    log_signal           = pyqtSignal(str)
    progress_signal      = pyqtSignal(int, int)
    result_signal        = pyqtSignal(dict)
    done_signal          = pyqtSignal()
    error_signal         = pyqtSignal(str)
    waiting_login_signal = pyqtSignal()
    step_signal          = pyqtSignal(str)   # current step description for status bar
    skip_signal          = pyqtSignal(str)   # username skipped as duplicate (§6)
    blocked_signal       = pyqtSignal()      # block/challenge detected (§5)

    def __init__(
        self,
        mode: str,
        search_term: str,
        count: int,
        min_followers: int,
        max_followers: int,
        excluded_set: set,
        selectors=None,
        app_settings: dict | None = None,
        *,
        fields: dict | None = None,
        web: dict | None = None,
        delays: dict | None = None,
        flow: dict | None = None,
        target: dict | None = None,
        resume_state: dict | None = None,
        cookies: list | None = None,
    ):
        super().__init__()
        self.mode          = mode
        self.search_term   = search_term
        self.count         = count
        self.min_followers = min_followers
        self.max_followers = max_followers
        self.excluded_set  = excluded_set

        from core import storage

        # ── v3 config groups (self-load when not injected, §9) ──────────────────
        self._web     = web    if web    is not None else storage.load_web()
        self._cookies = cookies or []
        self._delays = delays if delays is not None else storage.load_delays()
        self._flow   = flow   if flow   is not None else storage.load_flow()
        self._target = target if target is not None else storage.load_target()
        # Collectable profile fields (Fix-2 B): which fields ExtractProfile keeps.
        # ``username`` is always collected and is not part of this toggle set.
        self._collect_fields = fields if fields is not None else storage.load_fields()

        # Build step_id → row dict from selectors (list of dicts or None)
        rows = storage.load_selectors()
        if isinstance(selectors, list) and selectors:
            rows = selectors
        # Last-wins dict for backward-compat _get_by (single selector per step).
        self._selectors = {r["step_id"]: r for r in rows}
        # Priority fallback chains: step_id -> [row, ...] sorted by priority asc.
        self._selector_chains = self._build_selector_chains(rows)

        _s = app_settings or {}
        self._app_settings = _s

        # ── Flow knobs (§2.4) — app_settings overrides flow.csv when present ────
        def _flow_int(key, default):
            if key in _s:
                return int(_s.get(key))
            return int(self._flow.get(key, default))

        self.max_tags            = _flow_int("max_tags", 3)
        self.posts_per_tag       = _flow_int("posts_per_tag", 5)
        self.scroll_max_attempts = _flow_int("scroll_max_attempts", 15)
        self.tag_start_index     = _flow_int("tag_start_index", 0)
        self.stop_on_consecutive_miss = _flow_int("stop_on_consecutive_miss", 10)
        self.skip_visited_profile = _truthy(self._flow.get("skip_visited_profile", "true"))

        # ── Target filters (§2.5) — fall back to legacy min/max_followers ───────
        def _tgt_int(key, default):
            return int(self._target.get(key, default) or 0)

        self.min_following = _tgt_int("min_following", 0)
        self.max_following = _tgt_int("max_following", 0)
        self.min_posts     = _tgt_int("min_posts", 0)
        # min/max_followers already passed positionally; prefer non-zero target.
        if self.min_followers == 0:
            self.min_followers = _tgt_int("min_followers", 0)
        if self.max_followers == 0:
            self.max_followers = _tgt_int("max_followers", 0)

        # ── Resume state (§3.3 / §7) ────────────────────────────────────────────
        self._resume_state = resume_state
        self._start_tag_index  = self.tag_start_index
        self._start_post_index = 0
        self._collected        = 0
        self._seen: set[str]   = set()
        if resume_state:
            # Prefer the keyword/plan cursor when present (multi-keyword Fix-1);
            # fall back to the legacy tag_index key for older state files.
            self._start_tag_index  = int(resume_state.get(
                "keyword_index", resume_state.get("tag_index", self.tag_start_index)))
            self._start_post_index = int(resume_state.get("post_index", 0))
            self._collected        = int(resume_state.get("collected_count", 0))
            for u in resume_state.get("seen_usernames", []) or []:
                self._seen.add(self._norm_username(u))

        # Plan/keyword cursor for the multi-keyword tag loop (Fix-1). Persisted
        # alongside the legacy ``tag_index`` so resume can restore the keyword.
        self._current_plan_index = self._start_tag_index

        self._waiting_login = False
        self._stop          = False
        self._driver        = None

    # ── QThread control ───────────────────────────────────────────────────────

    def login_done(self):
        self._waiting_login = False

    def stop(self):
        self._stop = True

    # ── Logging ───────────────────────────────────────────────────────────────

    def _log(self, msg: str):
        self.log_signal.emit(msg)

    def _step(self, msg: str):
        self.step_signal.emit(msg)
        self._log(f"[step] {msg}")

    # ── Delays ────────────────────────────────────────────────────────────────

    def _random_delay(self, step_key: str):
        delays = getattr(self, "_delays", None) or {}
        if step_key in delays:
            min_sec, max_sec = delays[step_key]
            min_sec, max_sec = float(min_sec), float(max_sec)
        else:
            min_sec = float(self._app_settings.get(f"{step_key}_delay_min", 1.0))
            max_sec = float(self._app_settings.get(f"{step_key}_delay_max", 2.5))
        if max_sec < min_sec:
            max_sec = min_sec
        delay = random.uniform(min_sec, max_sec)
        self._log(f"  [delay/{step_key}] {delay:.1f}s")
        time.sleep(delay)

    def _typing_delay_range(self) -> tuple[float, float]:
        delays = getattr(self, "_delays", None) or {}
        lo, hi = delays.get("typing_char", (0.05, 0.18))
        return float(lo), float(hi)

    def _human_type(self, el, text: str):
        """Type ``text`` one character at a time with per-char random delay (§5)."""
        if not text:
            return
        lo, hi = self._typing_delay_range()
        if hi < lo:
            hi = lo
        for ch in text:
            el.send_keys(ch)
            time.sleep(random.uniform(lo, hi))

    # ── Selector helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _build_selector_chains(rows) -> dict:
        """Group selector rows by step_id, sorted by priority ascending."""
        chains: dict[str, list] = {}
        for row in (rows or []):
            sid = row.get("step_id")
            if not sid:
                continue
            chains.setdefault(sid, []).append(row)
        for sid, lst in chains.items():
            lst.sort(key=lambda r: (
                r.get("priority")
                if isinstance(r.get("priority"), int)
                else 9999
            ))
        return chains

    def _get_by(self, step_id: str):
        """Returns (selenium.By, selector_value) for the given step."""
        from selenium.webdriver.common.by import By
        row = self._selectors.get(step_id, {})
        sel_type  = (row.get("selector_type") or "xpath").lower()
        sel_value = _clean_selector_value(row.get("selector_value"))
        by = By.XPATH if sel_type == "xpath" else By.CSS_SELECTOR
        return by, sel_value

    def _resolve_selector(self, driver, step_id: str):
        """Try each candidate selector for step_id in priority order.

        Returns the first matching element. For a ``coord`` selector_type,
        returns a ``("coord", (x, y))`` tuple so the caller can fall back to a
        coordinate click. Returns ``None`` when nothing matches.
        """
        from selenium.webdriver.common.by import By
        chain = self._selector_chains.get(step_id, [])
        if not chain:
            self._log(f"  [selector] no selector chain for {step_id!r}")
            return None
        for row in chain:
            sel_type  = (row.get("selector_type") or "xpath").lower()
            sel_value = _clean_selector_value(row.get("selector_value"))
            priority  = row.get("priority")
            if sel_type == "coord":
                try:
                    x_str, y_str = str(sel_value).split(",")
                    coord = (float(x_str.strip()), float(y_str.strip()))
                    self._log(f"  [selector/{step_id}] priority {priority} coord fallback {coord}")
                    return ("coord", coord)
                except Exception:
                    self._log(f"  [selector/{step_id}] invalid coord {sel_value!r}")
                    continue
            by = By.XPATH if sel_type == "xpath" else By.CSS_SELECTOR
            try:
                els = driver.find_elements(by, sel_value)
            except Exception as exc:
                self._log(f"  [selector/{step_id}] priority {priority} error: {exc}")
                continue
            if els:
                self._log(
                    f"  [selector/{step_id}] priority {priority} matched {len(els)} element(s)"
                )
                return els[0]
        self._log(f"  [ERROR] [selector/{step_id}] all selectors failed")
        return None

    # ── Resume state (§3.3) ───────────────────────────────────────────────────

    def _save_state(self, tag_index: int, post_index: int):
        """Persist resume progress to state.json via storage (§3.3)."""
        from core import storage
        state = {
            "keyword": self.search_term.lstrip("#"),
            "tag_index": int(tag_index),
            "keyword_index": int(getattr(self, "_current_plan_index", tag_index)),
            "post_index": int(post_index),
            "collected_count": int(getattr(self, "_collected", 0)),
            "seen_usernames": sorted(getattr(self, "_seen", set())),
            "updated_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        }
        try:
            storage.save_state(state)
        except Exception as exc:
            self._log(f"  [state-err] {exc}")

    # ── Block detection (§5) ──────────────────────────────────────────────────

    def _is_blocked(self, driver) -> bool:
        """True if the session was redirected to a login/challenge/suspended
        page, indicating a block (§5). Distinct from the initial login wait."""
        try:
            url = (driver.current_url or "").lower()
        except Exception:
            return False
        return any(marker in url for marker in _BLOCKED_URL_MARKERS)

    # ── Dedup gate (§6) ───────────────────────────────────────────────────────

    @staticmethod
    def _norm_username(username: str) -> str:
        return (username or "").lstrip("@").strip().lower()

    def _should_skip(self, username: str) -> bool:
        """Early dedup gate: True if username already seen (results∪excluded∪seen).

        Emits ``skip_signal`` and logs on a hit. Does NOT mark the username as
        seen — callers add filter-failed usernames via ``self._seen.add(...)``.
        """
        norm = self._norm_username(username)
        seen = getattr(self, "_seen", None)
        if seen is None:
            seen = self._seen = set()
        if norm and norm in seen:
            self.skip_signal.emit(username)
            self._log(f"  [skip] 중복 건너뜀: @{norm}")
            return True
        return False

    # ── Backward-compat methods (used by tests) ───────────────────────────────

    def _passes_follower_filter(self, driver, username: str) -> tuple[bool, str]:
        if self.min_followers == 0 and self.max_followers == 0:
            return True, ""
        followers_str = get_follower_count(driver, username)
        f_num = parse_followers(followers_str)
        self._log(f"    followers: {f_num:,}  raw={followers_str!r}")
        if self.min_followers > 0 and f_num < self.min_followers:
            return False, followers_str
        if self.max_followers > 0 and f_num > self.max_followers:
            return False, followers_str
        return True, followers_str

    @staticmethod
    def _valid(candidate: str, blacklist: set) -> bool:
        return (
            candidate.lower() not in blacklist
            and len(candidate) >= 2
            and "official" not in candidate.lower()
        )

    _is_valid_username = _valid

    # ── Main run loop ─────────────────────────────────────────────────────────

    def run(self):
        """Infrastructure shell: launch browser, wait for login, build the seen
        set, then delegate the collection policy to a pluggable Flow (§flows).

        The per-mode orchestration (tag/post loops, dedup/filter/save) lives in
        ``core.flows`` — see ``get_flow(self.mode)``."""
        from core.flows import get_flow, ScrapeContext

        driver = None
        try:
            self._log("[browser] launching Chrome...")
            driver = init_driver(self._web, self._cookies)
            self._driver = driver

            driver.get("https://www.instagram.com/")
            time.sleep(3)

            self._log("[wait] Log in to Instagram, then click Login Done.")
            self._waiting_login = True
            self.waiting_login_signal.emit()
            while self._waiting_login and not self._stop:
                time.sleep(1)

            if self._stop:
                return

            time.sleep(2)

            # Build excluded set (UI list + CSV file)
            from core import storage
            excluded: set[str] = (
                {self._norm_username(u) for u in self.excluded_set}
                | {u.lower() for u in storage.load_excluded()}
            )

            # Unified seen set for early dedup gate (§6): results ∪ excluded
            # ∪ resume-state seed (already loaded into self._seen by __init__).
            self._seen |= {u for u in storage.seen_usernames()} | excluded

            if self._is_blocked(driver):
                self.blocked_signal.emit()
                self._log("[blocked] 차단 감지 - 일시정지")
                return

            # Delegate the collection policy to the registered Flow for this
            # mode ("keyword" aliases to the hashtag flow).
            self._blocked = False
            flow = get_flow(self.mode)
            flow.run(ScrapeContext(thread=self, driver=driver))

            # A mid-run block aborts without clearing resume state (§5/§7);
            # the flow already emitted blocked_signal + saved state.
            if self._blocked:
                return

            self._log(f"[done] collected {self._collected} accounts")
            # Normal completion → clear resume state (§7).
            try:
                storage.clear_state()
            except Exception:
                pass

        except Exception as exc:
            self.error_signal.emit(str(exc))
            self._log(f"[ERROR] {exc}")
        finally:
            self._waiting_login = False
            if driver:
                try:
                    driver.quit()
                except Exception:
                    pass
            self._driver = None
            self.done_signal.emit()
