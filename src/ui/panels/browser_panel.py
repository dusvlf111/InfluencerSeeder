"""Instagram 임베디드 브라우저 패널.

QWebEngineView + 영속 프로파일로 로그인 세션 보존.
모바일 UA를 사용해 Instagram 모바일 버전을 렌더링.
쿠키는 cookieAdded 신호로 수집 -> Selenium 쿠키 주입에 사용.
"""
from PyQt6.QtCore import QUrl
from PyQt6.QtWidgets import QMenu, QMessageBox
from PyQt6.QtWebEngineCore import (
    QWebEngineProfile, QWebEnginePage, QWebEngineSettings,
)
from PyQt6.QtWebEngineWidgets import QWebEngineView

import core.storage as storage

# 우클릭 좌표 등록 메뉴에 노출할 플로우 스텝(step_id, 라벨).
_COORD_STEPS = [
    ("search_icon",   "검색/탐색 아이콘"),
    ("search_input",  "검색어 입력창"),
    ("tag_result",    "태그 검색결과"),
    ("post_link",     "게시물(이미지)"),
    ("profile_link",  "프로필 이름/링크"),
    ("back_button",   "뒤로가기 버튼"),
]

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
# 모바일 임베딩이라 스크롤바는 CSS 로 숨긴다(아래 _HIDE_SCROLLBAR_JS) → 별도
# 여유 폭이 필요 없어 정확히 iPhone 12 의 75% 크기로 둔다.
_EMBED_W = round(_IPHONE_W * _EMBED_SCALE)   # 293
_EMBED_H = round(_IPHONE_H * _EMBED_SCALE)   # 633

# 임베디드 모바일 뷰의 스크롤바 제거(스크롤 자체는 가능, 막대만 비표시).
_HIDE_SCROLLBAR_JS = """
(function() {
    var id = '__embed_no_scrollbar__';
    if (document.getElementById(id)) return;
    var s = document.createElement('style');
    s.id = id;
    s.textContent =
        '*::-webkit-scrollbar{width:0!important;height:0!important;display:none!important;}' +
        'html,body{scrollbar-width:none!important;-ms-overflow-style:none!important;}';
    (document.head || document.documentElement).appendChild(s);
})();
"""


class BrowserPanel(QWebEngineView):
    """모바일 Instagram 임베디드 뷰 + 영속 세션.

    iPhone 12(390 x 844) 레이아웃을 75% 비율로 임베딩한다 — 뷰 위젯은 75% 크기
    (293 x 633)로 고정하고 zoomFactor 0.75 를 적용(프로그램 창 크기와 무관).
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        # 인스타 웹 뷰포트를 아이폰 12 의 75% 크기로 고정.
        self.setFixedSize(_EMBED_W, _EMBED_H)

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

        # 미디어 설정 — 인스타 영상/릴스는 자동재생이라 'PlaybackRequiresUserGesture'
        # 가 켜져 있으면 재생되지 않는다(영상 오류). 자동재생을 허용하고 관련
        # 기능을 켠다.
        self._configure_media(page.settings())

        # ⚠️ zoomFactor 는 setPage 로 페이지가 교체되면 1.0 으로 리셋되고, 페이지
        # 이동(load)마다도 초기화된다. 따라서 setPage 이후에 적용하고, 매 로드
        # 완료마다 재적용해야 75% 축소가 유지된다(안 그러면 100%로 보여 "확대"됨).
        self.setZoomFactor(_EMBED_SCALE)
        self.loadFinished.connect(self._reapply_zoom)

        self.load(QUrl(_HOME_URL))

    @staticmethod
    def _configure_media(settings):
        """영상 자동재생 허용 등 미디어 관련 WebEngine 설정.

        QWebEngineSettings 속성은 Qt 버전에 따라 일부가 없을 수 있으므로 각각
        존재할 때만 적용한다(예외 전파 금지)."""
        A = QWebEngineSettings.WebAttribute
        for name, value in (
            ("PlaybackRequiresUserGesture", False),  # 자동재생 허용(핵심)
            ("PluginsEnabled", True),
            ("WebGLEnabled", True),
            ("Accelerated2dCanvasEnabled", True),
            ("FullScreenSupportEnabled", True),
        ):
            attr = getattr(A, name, None)
            if attr is not None:
                try:
                    settings.setAttribute(attr, value)
                except Exception:
                    pass

    def _reapply_zoom(self, *_):
        """페이지 이동 후 줌이 리셋되므로 75% 를 다시 적용하고 스크롤바를 숨긴다."""
        self.setZoomFactor(_EMBED_SCALE)
        try:
            self.page().runJavaScript(_HIDE_SCROLLBAR_JS)
        except Exception:
            pass

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

    # ── 우클릭 → 좌표 등록 ───────────────────────────────────────────────────────

    def contextMenuEvent(self, event):
        """우클릭 위치를 특정 스텝의 coord 후보로 등록하는 메뉴를 띄운다.

        뷰는 zoom 0.75 로 렌더되므로 위젯 픽셀을 CSS 좌표(= elementFromPoint 가
        쓰는 좌표계)로 환산해 저장한다. 같은 임베디드 브라우저에서 클릭하므로
        좌표계가 일치한다."""
        pos = event.pos()
        css_x = round(pos.x() / _EMBED_SCALE)
        css_y = round(pos.y() / _EMBED_SCALE)

        menu = QMenu(self)
        sub = menu.addMenu(f"좌표 등록  ({css_x}, {css_y})")
        for step_id, label in _COORD_STEPS:
            act = sub.addAction(f"{label}  [{step_id}]")
            act.triggered.connect(
                lambda _checked=False, s=step_id, x=css_x, y=css_y:
                self._register_coord(s, x, y)
            )
        menu.exec(event.globalPos())

    def _register_coord(self, step_id: str, x: int, y: int):
        """선택한 스텝의 셀렉터 후보 맨 끝에 coord(x,y) 를 추가 저장한다."""
        try:
            rows = storage.load_selectors()
            # 같은 step_id 의 현재 최대 priority 다음 순번.
            prios = [r.get("priority", 0) for r in rows
                     if (r.get("step_id") or "") == step_id
                     and isinstance(r.get("priority"), int)]
            next_prio = (max(prios) + 1) if prios else 1
            name = next((lbl for sid, lbl in _COORD_STEPS if sid == step_id), step_id)
            rows.append({
                "step_id": step_id,
                "step_name": name,
                "priority": next_prio,
                "selector_type": "coord",
                "selector_value": f"{x},{y}",
            })
            storage.save_selectors(rows)
            QMessageBox.information(
                self, "좌표 등록됨",
                f"[{step_id}] 후보에 좌표 ({x}, {y}) 를 추가했습니다.\n"
                f"수집 시 셀렉터가 실패하면 이 좌표로 클릭합니다.",
            )
        except Exception as exc:
            QMessageBox.warning(self, "좌표 등록 실패", str(exc))
