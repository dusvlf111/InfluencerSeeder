"""Reusable Step implementations for the 6-step Instagram pipeline.

Each Step operates purely through ``ctx.thread`` (capability methods + signals)
and ``ctx.driver``. File I/O goes through ``core.storage``. Steps never touch UI
widgets — only ``ctx.thread.<signal>.emit(...)``. Behavior (log prefixes, signal
order, dedup/filter/save) mirrors the original ``ScraperThread.run()`` exactly.
"""

import re
import time
import datetime

from core.flows.base import Step, Outcome
from core.scraper_parsing import parse_followers, _BLACKLISTED_PATHS

# JavaScript: 게시물 페이지에서 /username/ 패턴 링크를 article > main > body 순으로 탐색.
_JS_FIND_PROFILE_USERNAME = """
(function() {
    var pat = /^\\/([A-Za-z0-9_.]{1,30})\\/$/;
    var bl = ['explore','p','reel','reels','stories','direct','accounts',
              'about','privacy','legal','terms','help','tv','tagged'];
    var containers = [
        document.querySelector('article header'),
        document.querySelector('article'),
        document.querySelector('main'),
        document.body
    ];
    for (var ci = 0; ci < containers.length; ci++) {
        var c = containers[ci];
        if (!c) continue;
        var links = c.querySelectorAll('a[href]');
        for (var i = 0; i < links.length; i++) {
            var h = (links[i].getAttribute('href') || '');
            var m = pat.exec(h);
            if (m && bl.indexOf(m[1]) === -1) return m[1];
        }
    }
    return null;
})()
"""


# ── Multi-keyword parsing (260610 Fix-1) ────────────────────────────────────────

def parse_keywords(search_term):
    """Split ``search_term`` into individual keywords.

    ``'인턴, 취준생\n개발자'`` → ``['인턴', '취준생', '개발자']`` — splits on commas
    and newlines, strips whitespace and a leading ``#``, drops empties and
    case-insensitive duplicates (preserving first-seen order). Always returns at
    least ``['']`` so the caller still runs one (empty) search."""
    out, seen = [], set()
    for raw in re.split(r"[,\n]", search_term or ""):
        k = raw.strip().lstrip("#").strip()
        if k and k.lower() not in seen:
            seen.add(k.lower())
            out.append(k)
    return out or [""]


def keyword_tag_plan(search_term, max_tags=1):
    """Build the (keyword, suggestion_index) plan for the tag loop.

    Each keyword maps to exactly one tag — the first suggestion (index 0). The
    plan length is the number of distinct keywords; ``max_tags`` is accepted for
    backward compatibility but no longer caps the loop (the overall cap is the
    collection ``count``)."""
    return [(kw, 0) for kw in parse_keywords(search_term)]


def click_coord(driver, thread, coord):
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
        thread._log(f"  [coord-err] click at {coord} failed: {exc}")


# ── Template param expansion (flow_steps ``param``) ─────────────────────────────

def _expand_param(ctx, param: str) -> str:
    """Expand a flow_steps ``param`` template against the live context.

    Supports ``#{keyword}`` / ``{keyword}`` / ``{tag_index}`` / ``{posts_per_tag}``.
    Unknown placeholders are left intact. Returns the raw param when no template
    markers are present (so plain literals/delay keys pass through unchanged)."""
    if not param:
        return ""
    t = ctx.thread
    mapping = {
        "keyword": getattr(ctx, "keyword", ""),
        "tag_index": getattr(ctx, "tag_index", 0),
        "posts_per_tag": getattr(t, "posts_per_tag", 0),
    }
    out = param
    for key, val in mapping.items():
        out = out.replace("#{" + key + "}", "#" + str(val))
        out = out.replace("{" + key + "}", str(val))
    return out


class ClickStep(Step):
    """Click the element resolved from ``selector_ref`` (coord fallback).

    Generalizes the original Step 1 (search icon). When ``selector_ref`` is the
    default ``search_icon`` and ``log_index`` is 1 the behavior — including the
    ``[1] search icon clicked`` log — is byte-for-byte identical."""

    def __init__(self, selector_ref: str = "search_icon", param: str = "",
                 log_index=1):
        self.selector_ref = selector_ref
        self.param = param
        self.log_index = log_index

    def execute(self, ctx) -> Outcome:
        t, driver = ctx.thread, ctx.driver
        ref = self.selector_ref or "search_icon"
        el = t._resolve_selector(driver, ref)
        if el is None:
            raise RuntimeError(f"{ref} selector chain exhausted")
        if isinstance(el, tuple) and el[0] == "coord":
            click_coord(driver, t, el[1])
        else:
            el.click()
        if ref == "search_icon":
            t._log("  [1] search icon clicked")
        else:
            t._log(f"  [{self.log_index}] clicked {ref}")
        return Outcome.CONTINUE


class TypeStep(Step):
    """Type ``param`` (template-expanded) into the input from ``selector_ref``.

    Generalizes the original Step 2. With the defaults (``search_input`` /
    ``#{keyword}``) it types ``#<keyword>`` and logs ``[2] typed #<keyword>``
    exactly as before."""

    def __init__(self, selector_ref: str = "search_input", param: str = "#{keyword}",
                 log_index=2):
        self.selector_ref = selector_ref
        self.param = param
        self.log_index = log_index

    def execute(self, ctx) -> Outcome:
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.common.exceptions import (
            ElementNotInteractableException,
            InvalidElementStateException,
            StaleElementReferenceException,
        )
        t, driver = ctx.thread, ctx.driver
        ref = self.selector_ref or "search_input"
        by, value = t._get_by(ref)
        text = _expand_param(ctx, self.param if self.param else "#{keyword}")

        # Resolve via the priority fallback chain first (tries the Korean
        # candidate before the English one); fall back to a single lookup.
        inp = t._resolve_selector(driver, ref)
        if inp is None or isinstance(inp, tuple):
            inp = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((by, value))
            )

        # The input must be interactable, not merely present: wait for it to
        # become clickable and focus it before typing (avoids the empty-message
        # ElementNotInteractable chromedriver error on the sliding search panel).
        try:
            inp = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((by, value)))
        except Exception:
            pass
        try:
            inp.click()
        except Exception:
            pass
        try:
            inp.clear()
        except (InvalidElementStateException, ElementNotInteractableException):
            pass

        # Instagram re-renders the search box as suggestions appear, which can
        # stale the element mid-typing — re-find and send the whole string once.
        try:
            t._human_type(inp, text)
        except StaleElementReferenceException:
            inp = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((by, value))
            )
            inp.send_keys(text)
        t._log(f"  [{self.log_index}] typed {text}")
        return Outcome.CONTINUE


class ClickIndexStep(Step):
    """Click the index-th matched element of ``selector_ref``.

    Generalizes the original Step 3. The index comes from ``param`` (template-
    expanded — default ``{tag_index}``) and falls back to ``ctx.tag_index``.
    Returns NEXT_TAG when the suggestion is unavailable, matching the original
    ``[3]`` logs."""

    def __init__(self, selector_ref: str = "tag_result", param: str = "{tag_index}",
                 log_index=3):
        self.selector_ref = selector_ref
        self.param = param
        self.log_index = log_index

    def _index(self, ctx) -> int:
        raw = _expand_param(ctx, self.param) if self.param else ""
        try:
            return int(str(raw).strip())
        except (ValueError, TypeError):
            return ctx.tag_index

    def execute(self, ctx) -> Outcome:
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        t, driver = ctx.thread, ctx.driver
        index = self._index(ctx)
        by, value = t._get_by(self.selector_ref or "tag_result")
        try:
            wait = WebDriverWait(driver, 10)
            wait.until(EC.presence_of_element_located((by, value)))
            time.sleep(0.6)   # let all suggestions load
            tags = driver.find_elements(by, value)
            if index >= len(tags):
                t._log(f"  [{self.log_index}] only {len(tags)} tag(s) found, need index {index}")
                return Outcome.NEXT_TAG
            label = tags[index].text.strip()
            tags[index].click()
            t._log(f"  [{self.log_index}] clicked tag suggestion [{index}]: {label!r}")
            return Outcome.CONTINUE
        except Exception as exc:
            t._log(f"  [{self.log_index}-err] {exc}")
            return Outcome.NEXT_TAG


# ── Backward-compatible aliases (fixed step_id defaults) ────────────────────────

class ClickSearchIcon(ClickStep):
    """Step 1 alias: click the search icon (``search_icon`` chain, coord fallback)."""

    def __init__(self):
        super().__init__(selector_ref="search_icon", log_index=1)


class TypeSearch(TypeStep):
    """Step 2 alias: type ``#{keyword}`` into the search input."""

    def __init__(self):
        super().__init__(selector_ref="search_input", param="#{keyword}", log_index=2)


class ClickTagSuggestion(ClickIndexStep):
    """Step 3 alias: click the ``ctx.tag_index``-th tag suggestion."""

    def __init__(self):
        super().__init__(selector_ref="tag_result", param="{tag_index}", log_index=3)


class CollectPostUrls(Step):
    """Step 4: Collect up to ``posts_per_tag`` post URLs from the tag grid.

    Stores the result in ``ctx.post_urls``.
    """

    def execute(self, ctx) -> Outcome:
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        t, driver = ctx.thread, ctx.driver
        target = t.posts_per_tag
        by, value = t._get_by("post_link")
        urls: list[str] = []
        seen_hrefs: set[str] = set()
        scroll_count = 0
        max_scrolls = 12

        try:
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((by, value)))
        except Exception:
            t._log("  [4] no posts found on tag grid")
            ctx.post_urls = urls
            return Outcome.CONTINUE

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

        t._log(f"  [4] collected {len(urls)} post URLs")
        ctx.post_urls = urls[:target]
        return Outcome.CONTINUE


class PeekUsernameGate(Step):
    """Early dedup gate (§6): peek the candidate username from the current post
    page WITHOUT navigating. Returns SKIP_POST if already seen."""

    def execute(self, ctx) -> Outcome:
        t, driver = ctx.thread, ctx.driver
        ctx.peeked_username = ""
        peeked = ""
        # 1. 설정된 셀렉터로 시도
        try:
            by, value = t._get_by("profile_link")
            els = driver.find_elements(by, value)
            for el in els:
                href = (el.get_attribute("href") or "").rstrip("/")
                username_part = href.split("/")[-1]
                if (
                    username_part
                    and username_part not in _BLACKLISTED_PATHS
                    and re.match(r'^[A-Za-z0-9_.]+$', username_part)
                ):
                    peeked = username_part
                    break
        except Exception:
            pass
        # 2. 셀렉터 실패 시 JS 폴백
        if not peeked:
            try:
                result = driver.execute_script(_JS_FIND_PROFILE_USERNAME)
                if result:
                    peeked = str(result).strip()
            except Exception:
                pass
        ctx.peeked_username = peeked
        if peeked and t._should_skip(peeked):
            return Outcome.SKIP_POST
        return Outcome.CONTINUE


class NavigateToProfile(Step):
    """Step 5: Find the profile link on the current post page and navigate to
    it. Stores the profile URL on ``ctx`` and returns SKIP_POST on failure."""

    def execute(self, ctx) -> Outcome:
        t, driver = ctx.thread, ctx.driver
        ctx.profile_url = ""
        username = ""

        # 1. 설정된 셀렉터 (timeout 5s로 줄여 지연 최소화)
        try:
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            by, value = t._get_by("profile_link")
            WebDriverWait(driver, 5).until(EC.presence_of_element_located((by, value)))
            els = driver.find_elements(by, value)
            for el in els:
                href = (el.get_attribute("href") or "").rstrip("/")
                u = href.split("/")[-1]
                if u and u not in _BLACKLISTED_PATHS and re.match(r'^[A-Za-z0-9_.]+$', u):
                    username = u
                    break
        except Exception:
            pass

        # 2. JS 폴백: article/main 내 /username/ 패턴 링크 탐색
        if not username:
            try:
                result = driver.execute_script(_JS_FIND_PROFILE_USERNAME)
                if result:
                    username = str(result).strip()
                    t._log(f"  [5-js] found via JS: @{username}")
            except Exception as exc:
                t._log(f"  [5-js-err] {exc}")

        # 3. PeekUsernameGate 에서 미리 추출한 username
        if not username:
            username = getattr(ctx, "peeked_username", "")
            if username:
                t._log(f"  [5-peek] using peeked username: @{username}")

        if username:
            profile_url = f"https://www.instagram.com/{username}/"
            try:
                t._log(f"  [5] navigating to profile: @{username}")
                driver.get(profile_url)
                ctx.profile_url = profile_url
                return Outcome.CONTINUE
            except Exception as exc:
                t._log(f"  [5-nav-err] {exc}")

        t._log("  [5-err] no profile link found — skipping post")
        return Outcome.SKIP_POST


class ExtractProfile(Step):
    """Step 6: Extract profile data from the current profile page. Stores the
    result dict on ``ctx.profile_info``; SKIP_POST when no username found."""

    @staticmethod
    def _active(ctx) -> set:
        """Set of profile fields the user opted to collect (Fix-2 B).

        ``username`` is always collected. When no toggle config is present
        (older threads / tests), every field is treated as active so behavior
        is unchanged."""
        cf = getattr(ctx.thread, "__dict__", {}).get("_collect_fields")
        if not isinstance(cf, dict):
            return None  # None == collect everything (backward compatible)
        active = {f for f, on in cf.items() if on}
        active.add("username")
        return active

    def execute(self, ctx) -> Outcome:
        from selenium.webdriver.common.by import By
        t, driver = ctx.thread, ctx.driver

        active = self._active(ctx)

        def _want(field: str) -> bool:
            return active is None or field in active

        result: dict = {}

        url = driver.current_url.rstrip("/")
        username_part = url.split("/")[-1]
        if not username_part or username_part in _BLACKLISTED_PATHS:
            ctx.profile_info = {}
            t._log("  [skip] could not extract username")
            return Outcome.SKIP_POST
        result["username"] = username_part

        try:
            meta = driver.find_element(By.XPATH, "//meta[@name='description']")
            content = meta.get_attribute("content") or ""
            m_f  = re.search(r"([\d,.万만천억]+)\s*(Followers|팔로워)",  content, re.IGNORECASE)
            m_fw = re.search(r"([\d,.万만천억]+)\s*(Following|팔로우|팔로잉)", content, re.IGNORECASE)
            m_p  = re.search(r"([\d,.万만천억]+)\s*(Posts|게시물)",       content, re.IGNORECASE)
            if m_f and _want("followers"):
                result["followers"] = m_f.group(1)
            if m_fw and _want("following"):
                result["following"] = m_fw.group(1)
            if m_p and _want("posts_count"):
                result["posts_count"] = m_p.group(1)
        except Exception:
            pass

        if "followers" not in result and (
            _want("followers") or _want("following") or _want("posts_count")
        ):
            try:
                src = driver.page_source
                for pat, key in [
                    (r'"edge_followed_by":\{"count":(\d+)\}',       "followers"),
                    (r'"edge_follow":\{"count":(\d+)\}',            "following"),
                    (r'"edge_owner_to_timeline_media":\{"count":(\d+)', "posts_count"),
                    (r'"follower_count":(\d+)',                     "followers"),
                ]:
                    m = re.search(pat, src)
                    if m and key not in result and _want(key):
                        result[key] = m.group(1)
            except Exception:
                pass

        if _want("bio"):
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

        if _want("website"):
            try:
                el = driver.find_element(
                    By.CSS_SELECTOR,
                    "header a[href*='http']:not([href*='instagram.com'])",
                )
                result["website"] = el.get_attribute("href") or ""
            except Exception:
                result["website"] = ""

        # ── Fallback: user-configured selectors (버튼매핑 탭) for empty fields ──────
        # Fills fields that meta/page_source/CSS heuristics left empty using the
        # priority selector chains from selectors.csv. Username stays URL-based;
        # this only augments. Failures are swallowed (existing values kept).
        self._fill_from_selectors(ctx, result, active)

        t._log(
            f"  [6] @{username_part}  "
            f"followers={result.get('followers', '?')}  "
            f"following={result.get('following', '?')}"
        )
        ctx.profile_info = result
        return Outcome.CONTINUE

    # field → (selector step_id, extraction mode)
    _SELECTOR_FALLBACKS = [
        ("full_name",   "username_text",   "text"),
        ("followers",   "followers_count", "count"),
        ("following",   "following_count", "count"),
        ("posts_count", "posts_count",     "count"),
        ("bio",         "bio_text",        "text"),
        ("website",     "website_link",    "href"),
    ]

    def _fill_from_selectors(self, ctx, result: dict, active=None) -> None:
        """Augment empty ``result`` fields via the configured selector chains.

        For each (field, step_id) pair, when ``result[field]`` is missing/empty,
        resolve the element through ``thread._resolve_selector`` (priority
        fallback, settings first) and read its text / title / href. Any error or
        empty value leaves the field untouched. Fields the user opted out of
        (``active`` set, Fix-2 B) are skipped entirely."""
        t, driver = ctx.thread, ctx.driver
        for field, step_id, mode in self._SELECTOR_FALLBACKS:
            if active is not None and field not in active:
                continue
            if result.get(field):
                continue
            try:
                el = t._resolve_selector(driver, step_id)
            except Exception:
                el = None
            if el is None or isinstance(el, tuple):
                continue
            value = ""
            try:
                if mode == "href":
                    value = (el.get_attribute("href") or "").strip() or (el.text or "").strip()
                elif mode == "count":
                    # follower/following/posts often live in a span @title.
                    value = (el.get_attribute("title") or "").strip() or (el.text or "").strip()
                else:  # text
                    value = (el.text or "").strip()
            except Exception:
                value = ""
            if value:
                if field == "bio":
                    value = value[:300]
                result[field] = value
                t._log(f"  [6/selector] {field} ← {step_id}")


class ApplyFilters(Step):
    """Follower-range filter (§2.5). On a filter miss the username is marked
    seen (§6) and SKIP_POST is returned. Reads ``ctx.profile_info``.

    The dedup gate (``_should_skip``) is handled by the Flow directly so it can
    preserve the original post-back-off timing for duplicate vs. filter cases.
    """

    def execute(self, ctx) -> Outcome:
        t = ctx.thread
        info = ctx.profile_info
        username = info["username"]

        if t.min_followers > 0 or t.max_followers > 0:
            f_num = parse_followers(info.get("followers", ""))
            if t.min_followers > 0 and f_num < t.min_followers:
                t._log(
                    f"  [filter] @{username} {f_num:,} < min {t.min_followers:,}"
                )
                t._seen.add(t._norm_username(username))
                return Outcome.SKIP_POST
            if t.max_followers > 0 and f_num > t.max_followers:
                t._log(
                    f"  [filter] @{username} {f_num:,} > max {t.max_followers:,}"
                )
                t._seen.add(t._norm_username(username))
                return Outcome.SKIP_POST

        return Outcome.CONTINUE


class SaveResult(Step):
    """Append the result (dedup via storage), emit signals, persist state."""

    def execute(self, ctx) -> Outcome:
        from core.storage import append_result
        t = ctx.thread
        info = ctx.profile_info
        username = info["username"]

        t._seen.add(t._norm_username(username))
        info["source_post_url"] = ctx.post_url
        info["post_url"]        = ctx.post_url
        info["profile_url"]     = ctx.profile_url
        info["source_tag"]      = ctx.keyword
        info["collected_at"]    = (
            datetime.datetime.now().astimezone().isoformat(timespec="seconds")
        )

        appended = append_result(info)
        if not appended:
            t._log(f"  [skip] @{username} duplicate (not counted)")
            return Outcome.SKIP_POST

        t.result_signal.emit(info)
        ctx.collected = ctx.collected + 1
        t.progress_signal.emit(ctx.collected, t.count)
        t._log(
            f"[OK] @{username}  "
            f"followers={info.get('followers', '?')}  "
            f"[{ctx.collected}/{t.count}]"
        )
        # Persist resume progress against the plan/keyword cursor (not the
        # suggestion index, which is 0 per keyword in the multi-keyword plan).
        t._save_state(getattr(ctx, "plan_index", ctx.tag_index), ctx.post_index + 1)
        return Outcome.CONTINUE


# ── New navigation Steps (260610-4) ─────────────────────────────────────────────

class OpenHomeIfNeeded(Step):
    """Navigate to the Instagram home page unless already on instagram.com.

    Lifts the inline ``if "instagram.com" not in driver.current_url`` guard that
    preceded Step 1 in the original HashtagFlow — same URL and 2s settle."""

    def execute(self, ctx) -> Outcome:
        driver = ctx.driver
        if "instagram.com" not in driver.current_url:
            driver.get("https://www.instagram.com/")
            time.sleep(2)
        return Outcome.CONTINUE


class GoBackStep(Step):
    """Return to the tag grid (default) or use the browser back button.

    Default (``param`` empty / ``grid``) reproduces the original
    ``driver.get(tag_grid_url)`` return; ``param == "back"`` calls
    ``driver.back()``. The post-back delay is driven by the Flow, not here."""

    def __init__(self, selector_ref: str = "", param: str = ""):
        self.selector_ref = selector_ref
        self.param = param

    def execute(self, ctx) -> Outcome:
        driver = ctx.driver
        mode = (self.param or "").strip().lower()
        if mode == "back":
            try:
                driver.back()
            except Exception as exc:
                ctx.thread._log(f"  [back-err] {exc}")
        else:
            if ctx.tag_grid_url:
                driver.get(ctx.tag_grid_url)
        return Outcome.CONTINUE


class ScrollStep(Step):
    """Random vertical scroll on the current page (used to load more content)."""

    def __init__(self, selector_ref: str = "", param: str = ""):
        self.selector_ref = selector_ref
        self.param = param

    def execute(self, ctx) -> Outcome:
        import random as _random
        t, driver = ctx.thread, ctx.driver
        amount = _random.randint(600, 1400)
        try:
            driver.execute_script(f"window.scrollBy(0, {amount});")
            t._log(f"  [scroll] {amount}px")
        except Exception as exc:
            t._log(f"  [scroll-err] {exc}")
        return Outcome.CONTINUE
