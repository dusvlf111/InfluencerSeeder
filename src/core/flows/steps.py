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


class ClickSearchIcon(Step):
    """Step 1: Click the search/magnifying-glass icon in the sidebar."""

    def execute(self, ctx) -> Outcome:
        t, driver = ctx.thread, ctx.driver
        el = t._resolve_selector(driver, "search_icon")
        if el is None:
            raise RuntimeError("search_icon selector chain exhausted")
        if isinstance(el, tuple) and el[0] == "coord":
            click_coord(driver, t, el[1])
        else:
            el.click()
        t._log("  [1] search icon clicked")
        return Outcome.CONTINUE


class TypeSearch(Step):
    """Step 2: Type the hashtag keyword in the search input."""

    def execute(self, ctx) -> Outcome:
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        t, driver = ctx.thread, ctx.driver
        by, value = t._get_by("search_input")
        wait = WebDriverWait(driver, 10)
        inp = wait.until(EC.presence_of_element_located((by, value)))
        inp.clear()
        t._human_type(inp, f"#{ctx.keyword}")
        t._log(f"  [2] typed #{ctx.keyword}")
        return Outcome.CONTINUE


class ClickTagSuggestion(Step):
    """Step 3: Click the index-th tag suggestion.

    Returns CONTINUE on success, NEXT_TAG when the suggestion is unavailable.
    """

    def execute(self, ctx) -> Outcome:
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        t, driver = ctx.thread, ctx.driver
        index = ctx.tag_index
        by, value = t._get_by("tag_result")
        try:
            wait = WebDriverWait(driver, 10)
            wait.until(EC.presence_of_element_located((by, value)))
            time.sleep(0.6)   # let all suggestions load
            tags = driver.find_elements(by, value)
            if index >= len(tags):
                t._log(f"  [3] only {len(tags)} tag(s) found, need index {index}")
                return Outcome.NEXT_TAG
            label = tags[index].text.strip()
            tags[index].click()
            t._log(f"  [3] clicked tag suggestion [{index}]: {label!r}")
            return Outcome.CONTINUE
        except Exception as exc:
            t._log(f"  [3-err] {exc}")
            return Outcome.NEXT_TAG


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
        by, value = t._get_by("profile_link")
        peeked = ""
        try:
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
        except Exception as exc:
            t._log(f"  [peek-err] {exc}")
        if peeked and t._should_skip(peeked):
            return Outcome.SKIP_POST
        return Outcome.CONTINUE


class NavigateToProfile(Step):
    """Step 5: Find the profile link on the current post page and navigate to
    it. Stores the profile URL on ``ctx`` and returns SKIP_POST on failure."""

    def execute(self, ctx) -> Outcome:
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        t, driver = ctx.thread, ctx.driver
        by, value = t._get_by("profile_link")
        ctx.profile_url = ""
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
                    t._log(f"  [5] navigating to profile: @{username_part}")
                    driver.get(profile_url)
                    ctx.profile_url = profile_url
                    return Outcome.CONTINUE
        except Exception as exc:
            t._log(f"  [5-err] {exc}")
        t._log("  [skip] no profile link found")
        return Outcome.SKIP_POST


class ExtractProfile(Step):
    """Step 6: Extract profile data from the current profile page. Stores the
    result dict on ``ctx.profile_info``; SKIP_POST when no username found."""

    def execute(self, ctx) -> Outcome:
        from selenium.webdriver.common.by import By
        t, driver = ctx.thread, ctx.driver

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
            if m_f:
                result["followers"] = m_f.group(1)
            if m_fw:
                result["following"] = m_fw.group(1)
            if m_p:
                result["posts_count"] = m_p.group(1)
        except Exception:
            pass

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

        try:
            el = driver.find_element(
                By.CSS_SELECTOR,
                "header a[href*='http']:not([href*='instagram.com'])",
            )
            result["website"] = el.get_attribute("href") or ""
        except Exception:
            result["website"] = ""

        t._log(
            f"  [6] @{username_part}  "
            f"followers={result.get('followers', '?')}  "
            f"following={result.get('following', '?')}"
        )
        ctx.profile_info = result
        return Outcome.CONTINUE


class ApplyFilters(Step):
    """Dedup + follower-range filter. On a filter miss the username is marked
    seen (§6) and SKIP_POST is returned. Reads ``ctx.profile_info``."""

    def execute(self, ctx) -> Outcome:
        t = ctx.thread
        info = ctx.profile_info
        username = info["username"]

        if t._should_skip(username):
            return Outcome.SKIP_POST

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
        t._save_state(ctx.tag_index, ctx.post_index + 1)
        return Outcome.CONTINUE
