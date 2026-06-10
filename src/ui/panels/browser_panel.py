"""Instagram 임베디드 브라우저 패널.

QWebEngineView + 영속 프로파일로 로그인 세션 보존.
모바일 UA를 사용해 Instagram 모바일 버전을 렌더링.
쿠키는 cookieAdded 신호로 수집 -> Selenium 쿠키 주입에 사용.
"""
from PyQt6.QtCore import QUrl
from PyQt6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage
from PyQt6.QtWebEngineWidgets import QWebEngineView

import core.storage as storage

_MOBILE_UA = (
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.6367.82 Mobile Safari/537.36"
)
_HOME_URL = "https://www.instagram.com/"

# 임베디드 웹뷰 고정 크기 — iPhone 12 Pro 논리 해상도(390 x 844, portrait).
# 프로그램 창이 아니라 "인스타 웹이 렌더되는 뷰포트"를 휴대폰 크기로 고정한다.
_IPHONE_W = 390
_IPHONE_H = 844


class BrowserPanel(QWebEngineView):
    """모바일 Instagram 임베디드 뷰 + 영속 세션.

    뷰 위젯 자체를 iPhone 12 Pro 크기(390 x 844)로 고정해 인스타 웹이 세로형
    휴대폰 뷰포트로 렌더되게 한다(프로그램 창 크기와 무관).
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        # 인스타 웹 뷰포트를 아이폰 크기로 고정(리사이즈해도 폰 크기 유지).
        self.setFixedSize(_IPHONE_W, _IPHONE_H)

        # 영속 프로파일 — data/browser_profile/ 에 쿠키/세션 저장
        profile_dir = str(storage.DATA_DIR / "browser_profile")
        self._profile = QWebEngineProfile("instagram_session", self)
        self._profile.setPersistentStoragePath(profile_dir)
        self._profile.setPersistentCookiesPolicy(
            QWebEngineProfile.PersistentCookiesPolicy.ForcePersistentCookies
        )
        self._profile.setHttpUserAgent(_MOBILE_UA)

        # 쿠키 수집 (Selenium 주입용)
        self._cookies: dict[str, dict] = {}
        store = self._profile.cookieStore()
        store.cookieAdded.connect(self._on_cookie_added)
        store.loadAllCookies()

        page = QWebEnginePage(self._profile, self)
        self.setPage(page)

        self.load(QUrl(_HOME_URL))

    def _on_cookie_added(self, cookie):
        name = bytes(cookie.name()).decode("utf-8", errors="replace")
        domain = cookie.domain()
        key = f"{domain}:{name}"
        self._cookies[key] = {
            "name": name,
            "value": bytes(cookie.value()).decode("utf-8", errors="replace"),
            "domain": domain,
            "path": cookie.path(),
            "secure": cookie.isSecure(),
            "httpOnly": cookie.isHttpOnly(),
        }

    def get_selenium_cookies(self) -> list[dict]:
        """Selenium driver.add_cookie() 형식 쿠키 목록 반환."""
        result = []
        for c in self._cookies.values():
            entry = {
                "name": c["name"],
                "value": c["value"],
                "domain": c["domain"],
                "path": c["path"],
                "secure": c["secure"],
            }
            result.append(entry)
        return result

    def navigate_home(self):
        """Instagram 홈으로 이동 (스크래핑 시작 전 초기화용)."""
        self.load(QUrl(_HOME_URL))
