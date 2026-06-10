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

# 임베디드 웹뷰 — iPhone 12 논리 해상도(390 x 844, portrait)를 75% 비율로 임베딩.
# 프로그램 창이 아니라 "인스타 웹이 렌더되는 뷰포트"를 휴대폰 크기로 고정한다.
# zoom 0.75 + 위젯크기=폰크기*0.75 → 페이지는 iPhone 12 폭(390 CSS px)으로
# 레이아웃되고 화면에는 75% 크기로 표시된다.
_IPHONE_W = 390
_IPHONE_H = 844
_EMBED_SCALE = 0.75
_EMBED_W = round(_IPHONE_W * _EMBED_SCALE)   # 293
_EMBED_H = round(_IPHONE_H * _EMBED_SCALE)   # 633


class BrowserPanel(QWebEngineView):
    """모바일 Instagram 임베디드 뷰 + 영속 세션.

    iPhone 12(390 x 844) 레이아웃을 75% 비율로 임베딩한다 — 뷰 위젯은 75% 크기
    (293 x 633)로 고정하고 zoomFactor 0.75 를 적용(프로그램 창 크기와 무관).
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        # 인스타 웹 뷰포트를 아이폰 12 의 75% 크기로 고정.
        self.setFixedSize(_EMBED_W, _EMBED_H)
        self.setZoomFactor(_EMBED_SCALE)

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
