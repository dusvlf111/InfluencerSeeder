import re
import time
import random
import datetime
from urllib.parse import quote

from PyQt6.QtCore import QThread, pyqtSignal


_BLACKLISTED_PATHS = {
    "instagram", "explore", "accounts", "p", "reel", "about",
    "help", "direct", "stories", "tv", "reels", "null", "undefined",
    "search", "privacy", "legal",
}

# Desktop Chrome user-agent pool for fingerprint randomization (§5).
_UA_POOL = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_4) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
]

# Window-size presets for fingerprint randomization (§5).
_WINDOW_PRESETS = [(1280, 900), (1440, 900), (1366, 768), (1536, 864)]

# URL fragments that indicate the session was redirected to a block/challenge.
_BLOCKED_URL_MARKERS = ("/accounts/login", "/challenge", "/accounts/suspended")


# ── Selenium utilities ────────────────────────────────────────────────────────

def _truthy(value) -> bool:
    """Interpret CSV-loaded values ('true'/'True'/True) as bool."""
    return str(value).strip().lower() == "true"


def _build_chrome_options(web: dict | None = None):
    """Construct Chrome Options honoring web.csv stealth toggles (§4/§5)."""
    from selenium.webdriver.chrome.options import Options
    web = web or {}
    options = Options()
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    if _truthy(web.get("headless")):
        options.add_argument("--headless=new")

    if _truthy(web.get("randomize_user_agent")):
        ua = random.choice(_UA_POOL)
        options.add_argument(f"--user-agent={ua}")

    if _truthy(web.get("randomize_window")):
        w, h = random.choice(_WINDOW_PRESETS)
        options.add_argument(f"--window-size={w},{h}")
    else:
        ww = web.get("window_width")
        wh = web.get("window_height")
        try:
            w = int(ww) if str(ww).strip() != "" else 1280
            h = int(wh) if str(wh).strip() != "" else 900
        except (TypeError, ValueError):
            w, h = 1280, 900
        if w > 0 and h > 0:
            options.add_argument(f"--window-size={w},{h}")
        else:
            # 0 means randomize per §2.1.
            w, h = random.choice(_WINDOW_PRESETS)
            options.add_argument(f"--window-size={w},{h}")

    user_data_dir = (web.get("user_data_dir") or "").strip() if isinstance(web.get("user_data_dir"), str) else web.get("user_data_dir")
    if user_data_dir:
        options.add_argument(f"--user-data-dir={user_data_dir}")

    return options


def _apply_stealth(driver):
    """Inject scripts to mask automation fingerprints (§5)."""
    try:
        driver.execute_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
    except Exception:
        pass
    try:
        driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {
                "source": "Object.defineProperty(navigator, 'webdriver', "
                          "{get: () => undefined})"
            },
        )
    except Exception:
        pass
    return driver


def init_driver(web: dict | None = None):
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from webdriver_manager.chrome import ChromeDriverManager

    if web is None:
        from core.storage import load_web
        web = load_web()

    options = _build_chrome_options(web)

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options,
    )
    try:
        pl_timeout = int(web.get("page_load_timeout") or 30)
        driver.set_page_load_timeout(pl_timeout)
    except Exception:
        pass
    try:
        iw = int(web.get("implicit_wait") or 0)
        if iw > 0:
            driver.implicitly_wait(iw)
    except Exception:
        pass
    _apply_stealth(driver)
    return driver


def parse_followers(text: str) -> int:
    """Convert '3.5만', '1,234', '12000' etc. to int."""
    if not text:
        return 0
    text = str(text).strip().replace(",", "").replace(" ", "")
    try:
        if "만" in text:
            return int(float(text.replace("만", "")) * 10_000)
        if "천" in text:
            return int(float(text.replace("천", "")) * 1_000)
        if "억" in text:
            return int(float(text.replace("억", "")) * 100_000_000)
        return int(float(text))
    except Exception:
        return 0


def get_follower_count(driver, username: str) -> str:
    """Return follower count string from profile page. Empty string on failure."""
    try:
        from selenium.webdriver.common.by import By
        driver.get(f"https://www.instagram.com/{username}/")
        time.sleep(2)
        try:
            meta = driver.find_element(By.XPATH, "//meta[@name='description']")
            content = meta.get_attribute("content") or ""
            m = re.search(r"([\d,.万만천억]+)\s*(Followers|팔로워)", content, re.IGNORECASE)
            if m:
                return m.group(1)
        except Exception:
            pass
        try:
            src = driver.page_source
            for pat in [
                r'"edge_followed_by":\{"count":(\d+)\}',
                r'"follower_count":(\d+)',
                r'"followers":(\d+)',
            ]:
                m = re.search(pat, src)
                if m:
                    return m.group(1)
        except Exception:
            pass
    except Exception:
        pass
    return ""


# ── ScraperThread ─────────────────────────────────────────────────────────────

class ScraperThread(QThread):
    log_signal           = pyqtSignal(str)
    progress_signal      = pyqtSignal(int, int)
    result_signal        = pyqtSignal(dict)
    done_signal          = pyqtSignal()
    error_signal         = pyqtSignal(str)
    waiting_login_signal = pyqtSignal()
    step_signal          = pyqtSignal(str)   # current step description for status bar

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
    ):
        super().__init__()
        self.mode          = mode
        self.search_term   = search_term
        self.count         = count
        self.min_followers = min_followers
        self.max_followers = max_followers
        self.excluded_set  = excluded_set

        # Build step_id → row dict from selectors (list of dicts or None)
        from core.storage import load_selectors
        rows = load_selectors()
        if isinstance(selectors, list) and selectors:
            rows = selectors
        # Last-wins dict for backward-compat _get_by (single selector per step).
        default_rows = {r["step_id"]: r for r in rows}
        self._selectors = default_rows
        # Priority fallback chains: step_id -> [row, ...] sorted by priority asc.
        self._selector_chains = self._build_selector_chains(rows)

        _s = app_settings or {}
        self.posts_per_tag = int(_s.get("posts_per_tag", 5))
        self.max_tags      = int(_s.get("max_tags", 3))
        self._app_settings = _s

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
        min_sec = float(self._app_settings.get(f"{step_key}_delay_min", 1.0))
        max_sec = float(self._app_settings.get(f"{step_key}_delay_max", 2.5))
        if max_sec < min_sec:
            max_sec = min_sec
        delay = random.uniform(min_sec, max_sec)
        self._log(f"  [delay/{step_key}] {delay:.1f}s")
        time.sleep(delay)

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
        sel_value = row.get("selector_value") or ""
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
            sel_value = row.get("selector_value") or ""
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

    # ── Step implementations ──────────────────────────────────────────────────

    def _step1_click_search_icon(self, driver):
        """Step 1: Click the search/magnifying-glass icon in the sidebar."""
        el = self._resolve_selector(driver, "search_icon")
        if el is None:
            raise RuntimeError("search_icon selector chain exhausted")
        if isinstance(el, tuple) and el[0] == "coord":
            self._click_coord(driver, el[1])
        else:
            el.click()
        self._log("  [1] search icon clicked")

    def _click_coord(self, driver, coord):
        """Click at an absolute (x, y) pixel coordinate via ActionChains."""
        x, y = coord
        from selenium.webdriver.common.action_chains import ActionChains
        from selenium.webdriver.common.actions.action_builder import ActionBuilder
        try:
            actions = ActionChains(driver)
            actions.w3c_actions = ActionBuilder(driver)
            actions.w3c_actions.pointer_action.move_to_location(int(x), int(y))
            actions.w3c_actions.pointer_action.click()
            actions.perform()
        except Exception as exc:
            self._log(f"  [coord-err] click at {coord} failed: {exc}")

    def _step2_type_search(self, driver, keyword: str):
        """Step 2: Type the hashtag keyword in the search input."""
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        by, value = self._get_by("search_input")
        wait = WebDriverWait(driver, 10)
        inp = wait.until(EC.presence_of_element_located((by, value)))
        inp.clear()
        inp.send_keys(f"#{keyword}")
        self._log(f"  [2] typed #{keyword}")

    def _step3_click_tag_suggestion(self, driver, index: int) -> bool:
        """Step 3: Click the index-th tag suggestion. Returns True on success."""
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        by, value = self._get_by("tag_result")
        try:
            wait = WebDriverWait(driver, 10)
            wait.until(EC.presence_of_element_located((by, value)))
            time.sleep(0.6)   # let all suggestions load
            tags = driver.find_elements(by, value)
            if index >= len(tags):
                self._log(f"  [3] only {len(tags)} tag(s) found, need index {index}")
                return False
            label = tags[index].text.strip()
            tags[index].click()
            self._log(f"  [3] clicked tag suggestion [{index}]: {label!r}")
            return True
        except Exception as exc:
            self._log(f"  [3-err] {exc}")
            return False

    def _step4_collect_post_urls(self, driver, target: int) -> list[str]:
        """Collect up to `target` post URLs from the current tag grid page."""
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        by, value = self._get_by("post_link")
        urls: list[str] = []
        seen_hrefs: set[str] = set()
        scroll_count = 0
        max_scrolls  = 12

        # Wait for first post to appear
        try:
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((by, value)))
        except Exception:
            self._log("  [4] no posts found on tag grid")
            return urls

        while len(urls) < target and scroll_count < max_scrolls:
            for el in driver.find_elements(by, value):
                href = (el.get_attribute("href") or "").split("?")[0]
                if href and "/p/" in href and href not in seen_hrefs:
                    seen_hrefs.add(href)
                    urls.append(href)
                if len(urls) >= target:
                    break
            if len(urls) >= target:
                break
            driver.execute_script("window.scrollBy(0, 1000);")
            time.sleep(1.5)
            scroll_count += 1

        self._log(f"  [4] collected {len(urls)} post URLs")
        return urls[:target]

    def _step5_navigate_to_profile(self, driver) -> str:
        """Step 5: Find profile link in current post page and navigate to it.
        Returns profile URL on success, empty string on failure."""
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        by, value = self._get_by("profile_link")
        try:
            WebDriverWait(driver, 8).until(EC.presence_of_element_located((by, value)))
            els = driver.find_elements(by, value)
            for el in els:
                href = (el.get_attribute("href") or "").rstrip("/")
                username_part = href.split("/")[-1]
                if (
                    username_part
                    and username_part not in _BLACKLISTED_PATHS
                    and re.match(r'^[A-Za-z0-9_.]+$', username_part)
                ):
                    profile_url = f"https://www.instagram.com/{username_part}/"
                    self._log(f"  [5] navigating to profile: @{username_part}")
                    driver.get(profile_url)
                    return profile_url
        except Exception as exc:
            self._log(f"  [5-err] {exc}")
        return ""

    def _step6_extract_profile(self, driver) -> dict:
        """Step 6: Extract profile data from the current profile page."""
        from selenium.webdriver.common.by import By

        result: dict = {}

        # Username from URL
        url = driver.current_url.rstrip("/")
        username_part = url.split("/")[-1]
        if not username_part or username_part in _BLACKLISTED_PATHS:
            return {}
        result["username"] = username_part

        # Meta description: "2,614 Posts, 16.7만 Followers, 0 Following - @user"
        try:
            meta = driver.find_element(By.XPATH, "//meta[@name='description']")
            content = meta.get_attribute("content") or ""
            m_f  = re.search(r"([\d,.万만천억]+)\s*(Followers|팔로워)",  content, re.IGNORECASE)
            m_fw = re.search(r"([\d,.万만천억]+)\s*(Following|팔로우|팔로잉)", content, re.IGNORECASE)
            m_p  = re.search(r"([\d,.万만천억]+)\s*(Posts|게시물)",       content, re.IGNORECASE)
            if m_f:
                result["followers"] = m_f.group(1)
            if m_fw:
                result["following"] = m_fw.group(1)
            if m_p:
                result["posts_count"] = m_p.group(1)
        except Exception:
            pass

        # Fallback: page-source JSON patterns
        if "followers" not in result:
            try:
                src = driver.page_source
                for pat, key in [
                    (r'"edge_followed_by":\{"count":(\d+)\}',       "followers"),
                    (r'"edge_follow":\{"count":(\d+)\}',            "following"),
                    (r'"edge_owner_to_timeline_media":\{"count":(\d+)', "posts_count"),
                    (r'"follower_count":(\d+)',                     "followers"),
                ]:
                    m = re.search(pat, src)
                    if m and key not in result:
                        result[key] = m.group(1)
            except Exception:
                pass

        # Bio from DOM (try several class patterns Instagram uses)
        _bio_selectors = [
            "span._ap3a._aaco._aacu._aacx._aad7._aade",
            "div._aacl._aaco._aacu._aacx._aad7._aade",
            "header section > div",
        ]
        for sel in _bio_selectors:
            try:
                el = driver.find_element(By.CSS_SELECTOR, sel)
                text = el.text.strip()
                if text:
                    result["bio"] = text[:300]
                    break
            except Exception:
                continue

        # Website link
        try:
            el = driver.find_element(
                By.CSS_SELECTOR,
                "header a[href*='http']:not([href*='instagram.com'])",
            )
            result["website"] = el.get_attribute("href") or ""
        except Exception:
            result["website"] = ""

        self._log(
            f"  [6] @{username_part}  "
            f"followers={result.get('followers', '?')}  "
            f"following={result.get('following', '?')}"
        )
        return result

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
        driver = None
        try:
            self._log("[browser] launching Chrome...")
            driver = init_driver()
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
            from core.storage import load_excluded, append_result
            excluded: set[str] = (
                {u.lstrip("@").lower() for u in self.excluded_set}
                | {u.lower() for u in load_excluded()}
            )

            # Avoid re-collecting accounts from previous runs
            from core.storage import load_results
            seen: set[str] = {r.get("username", "") for r in load_results() if r.get("username")}

            keyword   = self.search_term.lstrip("#")
            collected = 0

            for tag_index in range(self.max_tags):
                if self._stop or collected >= self.count:
                    break

                # Always start from home page for search icon
                if "instagram.com" not in driver.current_url:
                    driver.get("https://www.instagram.com/")
                    time.sleep(2)

                # --- Step 1 ---
                self._step(f"Step 1/6 — Clicking search icon  (tag {tag_index + 1}/{self.max_tags})")
                try:
                    self._step1_click_search_icon(driver)
                except Exception as exc:
                    self._log(f"  [step1-err] {exc}")
                    break
                self._random_delay("step1")

                # --- Step 2 ---
                self._step(f"Step 2/6 — Typing #{keyword}")
                try:
                    self._step2_type_search(driver, keyword)
                except Exception as exc:
                    self._log(f"  [step2-err] {exc}")
                    break
                self._random_delay("step2")

                # --- Step 3 ---
                self._step(f"Step 3/6 — Selecting tag suggestion #{tag_index + 1}")
                ok = self._step3_click_tag_suggestion(driver, tag_index)
                if not ok:
                    self._log(f"  [stop] no tag suggestion at index {tag_index}")
                    break
                self._random_delay("step3")

                tag_grid_url = driver.current_url
                self._log(f"[grid] {tag_grid_url}")

                # --- Step 4 (collect URLs) ---
                self._step(f"Step 4/6 — Collecting post URLs from tag grid")
                post_urls = self._step4_collect_post_urls(driver, self.posts_per_tag)

                for post_idx, post_url in enumerate(post_urls):
                    if self._stop or collected >= self.count:
                        break

                    # --- Step 4 (navigate to post) ---
                    self._step(
                        f"Step 4/6 — Opening post {post_idx + 1}/{len(post_urls)}"
                        f"  (tag {tag_index + 1})"
                    )
                    self._log(f"[4] {post_url}")
                    try:
                        driver.get(post_url)
                    except Exception as exc:
                        self._log(f"  [4-err] {exc}")
                        continue
                    self._random_delay("step4")

                    # --- Step 5 ---
                    self._step("Step 5/6 — Navigating to profile")
                    profile_url = self._step5_navigate_to_profile(driver)
                    if not profile_url:
                        self._log("  [skip] no profile link found")
                        driver.get(tag_grid_url)
                        time.sleep(1.5)
                        continue
                    self._random_delay("step5")

                    # --- Step 6 ---
                    self._step("Step 6/6 — Saving profile data")
                    info = self._step6_extract_profile(driver)

                    if not info or not info.get("username"):
                        self._log("  [skip] could not extract username")
                        driver.get(tag_grid_url)
                        time.sleep(1.5)
                        continue

                    username = info["username"]

                    if username.lower() in excluded:
                        self._log(f"  [skip] @{username} is excluded")
                        driver.get(tag_grid_url)
                        time.sleep(1.0)
                        continue
                    if username in seen:
                        self._log(f"  [skip] @{username} already collected")
                        driver.get(tag_grid_url)
                        time.sleep(1.0)
                        continue

                    # Follower filter
                    if self.min_followers > 0 or self.max_followers > 0:
                        f_num = parse_followers(info.get("followers", ""))
                        if self.min_followers > 0 and f_num < self.min_followers:
                            self._log(
                                f"  [filter] @{username} {f_num:,} < min {self.min_followers:,}"
                            )
                            driver.get(tag_grid_url)
                            continue
                        if self.max_followers > 0 and f_num > self.max_followers:
                            self._log(
                                f"  [filter] @{username} {f_num:,} > max {self.max_followers:,}"
                            )
                            driver.get(tag_grid_url)
                            continue

                    seen.add(username)
                    info["post_url"]     = post_url
                    info["profile_url"]  = profile_url
                    info["collected_at"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                    append_result(info)
                    self.result_signal.emit(info)
                    collected += 1
                    self.progress_signal.emit(collected, self.count)
                    self._log(
                        f"[OK] @{username}  "
                        f"followers={info.get('followers', '?')}  "
                        f"[{collected}/{self.count}]"
                    )
                    self._random_delay("step6")

                    # Back to tag grid
                    self._step("Returning to tag grid...")
                    driver.get(tag_grid_url)
                    self._random_delay("back")

            self._log(f"[done] collected {collected} accounts")

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
