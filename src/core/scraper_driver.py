"""Chrome driver construction + stealth fingerprinting (§4/§5).

Extracted from scraper.py. ``random`` is imported at module level so the
``patch("core.scraper.random.choice", ...)`` contract keeps working (random is
a singleton — patching it on any importing module affects the shared object).
``core.scraper`` re-exports everything here.
"""

import random


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

    # Renderer 안정화 — "Timed out receiving message from renderer" 완화.
    # Instagram 은 백그라운드 요청이 끊이지 않아 'normal' 로드 전략에선
    # driver.get() 이 완료를 못 받고 렌더러 타임아웃이 난다. 'eager' 는 DOM
    # 준비(DOMContentLoaded) 시점에 반환하므로 이를 피한다.
    options.page_load_strategy = "eager"
    options.add_argument("--disable-dev-shm-usage")  # /dev/shm 고갈로 인한 렌더러 크래시 방지
    options.add_argument("--disable-gpu")            # GPU 프로세스發 렌더러 행 방지

    if _truthy(web.get("headless")):
        options.add_argument("--headless=new")

    _MOBILE_UA = (
        "Mozilla/5.0 (Linux; Android 13; Pixel 7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.6367.82 Mobile Safari/537.36"
    )

    if _truthy(web.get("mobile_ua")):
        options.add_argument(f"--user-agent={_MOBILE_UA}")
        # 모바일 뷰포트 + 터치 에뮬레이션
        options.add_argument("--window-size=390,844")
        mobile_emulation = {
            "deviceMetrics": {"width": 390, "height": 844, "pixelRatio": 3.0},
            "userAgent": _MOBILE_UA,
        }
        options.add_experimental_option("mobileEmulation", mobile_emulation)
    elif _truthy(web.get("randomize_user_agent")):
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


def _inject_cookies(driver, cookies: list[dict]):
    """임베디드 브라우저에서 추출한 쿠키를 Selenium Chrome에 주입."""
    if not cookies:
        return
    try:
        # 쿠키 설정을 위해 인스타 도메인에 있어야 함
        driver.get("https://www.instagram.com/")
        for cookie in cookies:
            try:
                c = {k: v for k, v in cookie.items()
                     if k in ("name", "value", "domain", "path", "secure")}
                # domain이 .instagram.com 형태면 그대로, 아니면 조정
                if c.get("domain", "").startswith("."):
                    c["domain"] = c["domain"]
                driver.add_cookie(c)
            except Exception:
                pass
        driver.refresh()
    except Exception:
        pass


def init_driver(web: dict | None = None, cookies: list[dict] | None = None):
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
    if cookies:
        _inject_cookies(driver, cookies)
    return driver
