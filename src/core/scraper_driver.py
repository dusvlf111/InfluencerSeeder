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
    options.add_argument("--no-sandbox")             # 렌더러 기동 실패 완화

    if _truthy(web.get("headless")):
        options.add_argument("--headless=new")
        # --disable-gpu 는 headless 에서만. headful Chrome(149+) + 모바일
        # 에뮬레이션과 함께 쓰면 "Timed out receiving message from renderer"
        # 렌더러 행을 유발하므로 창 모드에서는 추가하지 않는다.
        options.add_argument("--disable-gpu")

    # iPhone 12 Pro 디바이스 에뮬레이션 — 논리 해상도 390x844, DPR 3, iOS Safari UA.
    # (Chrome DevTools 의 "iPhone 12 Pro" 프리셋과 동일한 메트릭/UA)
    _IPHONE_UA = (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Version/17.5 Mobile/15E148 Safari/604.1"
    )

    mobile = _truthy(web.get("mobile_ua"))
    if mobile:
        # UA 는 mobileEmulation 안에서만 지정한다. --user-agent 인자와 동시에
        # 주면 UA 가 이중 설정돼 렌더러가 혼란/행에 빠질 수 있다(중복 제거).
        options.add_argument("--window-size=390,844")
        mobile_emulation = {
            "deviceMetrics": {"width": 390, "height": 844, "pixelRatio": 3.0},
            "userAgent": _IPHONE_UA,
        }
        options.add_experimental_option("mobileEmulation", mobile_emulation)
    elif _truthy(web.get("randomize_user_agent")):
        ua = random.choice(_UA_POOL)
        options.add_argument(f"--user-agent={ua}")

    # 모바일 에뮬레이션이 켜지면 창 크기는 390x844 로 이미 고정했으므로,
    # randomize_window/창크기 프리셋이 이를 덮어쓰지 않도록 건너뛴다.
    if mobile:
        pass
    elif _truthy(web.get("randomize_window")):
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
