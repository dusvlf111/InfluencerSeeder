"""Follower/profile text parsing helpers (pure, network-free).

Used by the embedded scraper (``core.embedded_scraper``). The previous
Selenium-driven reader was removed along with the Selenium engine.
"""

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
