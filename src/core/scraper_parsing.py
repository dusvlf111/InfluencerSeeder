"""Follower/profile text parsing helpers extracted from scraper.py.

These are pure (network-free) parsing utilities plus the single Selenium-driven
``get_follower_count`` reader. ``get_follower_count`` is re-exported from
``core.scraper`` so the ``patch("core.scraper.get_follower_count", ...)``
contract used by ``_passes_follower_filter`` tests keeps working.
"""

import re
import time


_BLACKLISTED_PATHS = {
    "instagram", "explore", "accounts", "p", "reel", "about",
    "help", "direct", "stories", "tv", "reels", "null", "undefined",
    "search", "privacy", "legal",
}


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
