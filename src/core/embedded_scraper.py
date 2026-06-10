"""임베디드 브라우저(QtWebEngine) 기반 수집 엔진 — 마우스 클릭 방식.

Selenium(별도 Chrome) 대신, 이미 열려 로그인된 임베디드 BrowserPanel 안에서
JavaScript 로 **실제 클릭**해 단계를 진행한다(URL 직접 이동 X → 봇 탐지 회피).

각 스텝은 ``selectors.csv`` 의 후보를 **위→아래 순서로 시도**하고(css/xpath),
모두 실패하면 **좌표(coord) 클릭**으로 폴백한다. 이상한 모달이 뜨면 닫기 버튼을
눌러 제거한다. 단계 사이에는 랜덤 딜레이를 적용한다.

이 모듈은 ``PyQt6.QtCore`` 만 의존(항상 사용 가능)하고, QtWebEngine 은 호출부가
넘겨준 ``browser`` 객체(QWebEngineView)를 통해서만 사용한다 — 그래서 WebEngine 이
없는 환경에서도 import/단위테스트가 가능하다. 순수 로직(JS 생성/메타 파싱)은
모듈 레벨 함수로 분리해 테스트한다.
"""

import json
import re

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from core.scraper_parsing import parse_followers, _BLACKLISTED_PATHS

_HOME_URL = "https://www.instagram.com/"

# 모달/팝업 '나중에/거절' 류 라벨만(검색 닫기·취소 등 일반 닫기 버튼은 제외 —
# 그걸 누르면 검색창이 닫혀버린다). 알림 켜기/로그인정보 저장 팝업만 닫는다.
_DISMISS_LABELS = [
    "Not Now", "Not now", "나중에 하기", "나중에", "나중에 다시 알림",
    "지금 안 함", "정보 저장 안 함",
]


# ── Pure helpers (QtWebEngine 불필요 — 단위테스트 대상) ─────────────────────────

def candidates_for(selectors: list[dict], step_id: str) -> list[dict]:
    """selectors.csv 행들에서 ``step_id`` 후보를 priority 순으로 [{type,value}]."""
    out = []
    for row in selectors or []:
        if (row.get("step_id") or "") != step_id:
            continue
        out.append({
            "type": (row.get("selector_type") or "xpath").lower(),
            "value": row.get("selector_value") or "",
        })
    return out


def build_click_js(candidates: list[dict]) -> str:
    """후보들을 순서대로 시도해 첫 매칭 요소를 클릭하는 JS. 성공 시 후보 index,
    실패 시 -1 을 반환한다. coord 후보는 ``elementFromPoint`` 로 좌표 클릭."""
    payload = json.dumps(candidates, ensure_ascii=False)
    return _CLICK_FN + f"return __tryClick({payload});}})()"


def build_type_js(candidates: list[dict], text: str) -> str:
    """후보 입력창을 찾아 사람처럼 값을 넣는 JS(React 호환: native setter + input
    이벤트). 성공 true/실패 false."""
    payload = json.dumps(candidates, ensure_ascii=False)
    txt = json.dumps(text, ensure_ascii=False)
    return _FIND_FN + f"""
        var el = __findFirst({payload});
        if (!el) return false;
        el.focus();
        try {{
            var d = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value');
            (d && d.set ? d.set : function(v){{ this.value = v; }}).call(el, {txt});
        }} catch (e) {{ el.value = {txt}; }}
        el.dispatchEvent(new Event('input', {{bubbles: true}}));
        el.dispatchEvent(new Event('change', {{bubbles: true}}));
        return true;
    }})()"""


def build_click_index_js(candidates: list[dict], index: int) -> str:
    """후보 셀렉터로 매칭된 요소 중 index 번째를 클릭(css/xpath). 성공 true/실패 false."""
    payload = json.dumps(candidates, ensure_ascii=False)
    return _CLICK_INDEX_FN + f"return __clickIndex({payload}, {int(index)});}})()"


def build_count_js(candidates: list[dict]) -> str:
    """후보로 매칭되는 요소 개수(첫 매칭 후보 기준)."""
    payload = json.dumps(candidates, ensure_ascii=False)
    return _COUNT_FN + f"return __count({payload});}})()"


def build_rect_js(candidates: list[dict]) -> str:
    """첫 매칭 요소를 화면 안으로 스크롤한 뒤 중심 좌표(CSS) {x,y} 반환(없으면 null).
    실제 Qt 마우스 클릭(real_click_css)에 넘길 좌표를 얻는 데 쓴다."""
    payload = json.dumps(candidates, ensure_ascii=False)
    return _FIND_FN + f"""
        var el = __findFirst({payload});
        if (!el) return null;
        try {{ el.scrollIntoView({{block: 'center', inline: 'center'}}); }} catch (e) {{}}
        var r = el.getBoundingClientRect();
        if (!r || (r.width === 0 && r.height === 0)) return null;
        return {{x: r.left + r.width / 2, y: r.top + r.height / 2}};
    }})()"""


def dismiss_popup_js() -> str:
    labels = json.dumps(_DISMISS_LABELS, ensure_ascii=False)
    return f"""(function(){{
        var labels = {labels};
        var n = 0;
        var btns = document.querySelectorAll("button, div[role='button']");
        for (var i = 0; i < btns.length; i++) {{
            var t = (btns[i].innerText || '').trim();
            if (labels.indexOf(t) !== -1) {{
                try {{ btns[i].click(); n++; }} catch (e) {{}}
            }}
        }}
        return n;
    }})()"""


_PEEK_USERNAME_JS = """
(function(){
    var bl = %s;
    var pat = /^\\/([A-Za-z0-9_.]{1,30})\\/$/;
    var cs = [document.querySelector('article header'),
              document.querySelector('article'),
              document.querySelector('main'), document.body];
    for (var ci = 0; ci < cs.length; ci++) {
        var c = cs[ci]; if (!c) continue;
        var ls = c.querySelectorAll("a[href]");
        for (var i = 0; i < ls.length; i++) {
            var h = ls[i].getAttribute('href') || '';
            var m = pat.exec(h);
            if (m && bl.indexOf(m[1]) === -1) return m[1];
        }
    }
    return null;
})()
""" % json.dumps(sorted(_BLACKLISTED_PATHS))


# 현재 페이지 종류를 URL(pathname) 기준으로 판별:
# login / tag(태그 그리드) / explore(검색·탐색) / post(게시물) / home / profile / unknown
_PAGE_STATE_JS = r"""
(function(){
    var p = location.pathname || "";
    if (/\/accounts\/login|\/challenge|\/accounts\/suspended/.test(p)) return "login";
    if (/^\/explore\/tags\//.test(p)) return "tag";
    if (/^\/explore\//.test(p)) return "explore";
    if (/^\/(p|reel)\//.test(p)) return "post";
    if (p === "/" || p === "") return "home";
    var seg = p.replace(/^\/|\/$/g, "").split("/");
    var bl = ["explore","p","reel","reels","stories","direct","accounts",
              "about","privacy","legal","terms","help","tv","tagged"];
    if (seg.length === 1 && seg[0] && bl.indexOf(seg[0]) === -1) return "profile";
    return "unknown";
})()
"""


_PROFILE_JS = """
(function(){
    var meta = document.querySelector("meta[name='description']");
    var bio = document.querySelector("header section > div:last-child")
              || document.querySelector("header div[dir]");
    var site = document.querySelector("header a[href*='http']:not([href*='instagram.com'])");
    return {
        url: location.href,
        meta: meta ? (meta.getAttribute('content') || '') : '',
        bio: bio ? (bio.innerText || '') : '',
        website: site ? (site.getAttribute('href') || '') : ''
    };
})()
"""


# 숫자는 반드시 자릿수로 시작(쉼표/마침표가 라벨 앞에서 오매칭되는 것 방지).
_NUM = r"\d[\d,.，万만천억]*"


def _num_for(text: str, label: str) -> str:
    """meta description 에서 ``label`` 에 해당하는 숫자 추출. 영어(숫자→라벨)와
    한국어(라벨→숫자) 양쪽 순서를 모두 시도한다."""
    if not text:
        return ""
    # 숫자 → 라벨 (예: '3,632 Followers')
    m = re.search(rf"({_NUM})\s*(?:{label})", text, re.IGNORECASE)
    if m:
        return m.group(1).strip(",.  ")
    # 라벨 → 숫자 (예: '팔로워 3,632명')
    m = re.search(rf"(?:{label})\s*({_NUM})", text, re.IGNORECASE)
    if m:
        return m.group(1).strip(",.  ")
    return ""


def build_profile_js(selectors: list[dict]) -> str:
    """프로필 정보를 **DOM 셀렉터**로 추출하는 JS(SPA 라 meta description 은
    홈 그대로라 못 씀). username_text/followers_count/following_count/
    posts_count/bio_text/website_link 후보를 사용. count 류는 span[title] 의
    title 속성을 우선 사용한다."""
    fields = {
        "username": candidates_for(selectors, "username_text"),
        "followers": candidates_for(selectors, "followers_count"),
        "following": candidates_for(selectors, "following_count"),
        "posts_count": candidates_for(selectors, "posts_count"),
        "bio": candidates_for(selectors, "bio_text"),
    }
    web = candidates_for(selectors, "website_link")
    fpayload = json.dumps(fields, ensure_ascii=False)
    wpayload = json.dumps(web, ensure_ascii=False)
    return _FIND_FN + f"""
        function __txt(cands){{
            // 후보를 순서대로 시도하되, 매칭돼도 텍스트가 비면 다음 후보로 넘어간다
            // (빈 래퍼 요소를 먼저 잡아 빈 값을 반환하던 버그 방지).
            for (var i = 0; i < cands.length; i++){{
                var el = __first(cands[i]); if (!el) continue;
                var t = (el.getAttribute && el.getAttribute('title')) || "";
                if (!t) t = (el.innerText || el.textContent || "");
                t = (t || "").trim();
                if (t) return t;
            }}
            return "";
        }}
        // 소개글 폴백: 설정 셀렉터가 빈 값일 때 헤더에서 내용 기반으로 bio 추출.
        // 클래스명(난독화)에 의존하지 않아 IG DOM 변경에도 견딘다. 유저네임/카운트/
        // 버튼/링크 줄을 제외한 leaf 텍스트 중 가장 긴 것을 bio 로 본다(카테고리 줄
        // 보다 실제 소개글이 길다).
        function __headerBio(){{
            var root = document.querySelector('header') || document.querySelector('main');
            if (!root) return "";
            var uname = (location.pathname || "").replace(/^\\/|\\/$/g, '').split('/')[0].toLowerCase();
            var nodes = root.querySelectorAll('span[dir], h1[dir], h1, div[dir]');
            var best = "";
            for (var i = 0; i < nodes.length; i++){{
                var el = nodes[i];
                if (el.closest('a, button, [role=button], [role=link]')) continue;
                if (el.querySelector('span[dir], h1[dir], div[dir], a, button')) continue; // leaf 만
                var t = (el.innerText || el.textContent || "").replace(/\\u00a0/g, ' ').trim();
                if (!t || t.length < 2) continue;
                if (t.toLowerCase() === uname) continue;                       // 유저네임
                if (/^@?[A-Za-z0-9_.]{{1,30}}$/.test(t)) continue;             // 핸들/아이디만
                if (/\\d/.test(t) && /(게시물|팔로워|팔로우|posts|followers|following)/i.test(t)) continue; // 카운트 줄
                if (/^(팔로우|팔로잉|메시지(\\s*보내기)?|follow|following|message)$/i.test(t)) continue;   // 버튼
                if (/외\\s*\\d+\\s*개$/.test(t)) continue;                     // "vo.la/.. 외 4개" 링크 요약
                if (t.length > best.length) best = t;
            }}
            return best;
        }}
        var fields = {fpayload}; var out = {{}};
        for (var k in fields) out[k] = __txt(fields[k]);
        if (!out.bio) out.bio = __headerBio();
        var w = __findFirst({wpayload});
        out.website = w ? (w.getAttribute('href') || "") : "";
        out.url = location.href;
        return out;
    }})()"""


def _clean_num(text: str) -> str:
    """텍스트에서 첫 숫자 토큰만 추출('팔로워 3,632명' → '3,632')."""
    if not text:
        return ""
    m = re.search(_NUM, str(text))
    return m.group(0).strip(",.  ") if m else ""


def parse_profile(data: dict) -> dict:
    """프로필 JS 결과({url,meta,bio,website})를 results 스키마 dict 로 파싱.

    username 은 URL 에서, 팔로워/팔로우/게시물 수는 meta description 에서 추출한다.
    """
    out: dict = {}
    url = (data.get("url") or "").rstrip("/").split("?")[0]
    username = url.split("/")[-1] if url else ""
    if not username or username in _BLACKLISTED_PATHS:
        # URL 로 못 얻으면 username_text 필드에서 보조 추출.
        username = (data.get("username") or "").lstrip("@").strip()
    if not username or username in _BLACKLISTED_PATHS:
        return {}
    out["username"] = username
    # 프로필 진입 후의 실제 URL 을 기록(없으면 표준형으로 구성).
    out["profile_url"] = url if url.startswith("http") else f"https://www.instagram.com/{username}/"

    # DOM 필드(build_profile_js) 우선, 없으면 meta description 폴백.
    content = data.get("meta") or ""
    fol = _clean_num(data.get("followers")) or _num_for(content, r"Followers|팔로워")
    fwg = _clean_num(data.get("following")) or _num_for(content, r"Following|팔로잉|팔로우")
    pst = _clean_num(data.get("posts_count")) or _num_for(content, r"Posts|게시물")
    if fol:
        out["followers"] = fol
    if fwg:
        out["following"] = fwg
    if pst:
        out["posts_count"] = pst

    bio = (data.get("bio") or "").strip()
    if bio:
        out["bio"] = bio[:300]
    out["website"] = data.get("website") or ""
    return out


# ── 현재 위치(페이지) → 재개 진입점 매핑 ────────────────────────────────────────
# '지금 창이 어느 플로우에 있는지' 확인해 거기서부터 다시 시작하기 위한 라우팅.
# 이 매핑이 동작 정책의 단일 출처 — 여기를 고치면 재개 동작이 바뀐다.
#   search  : 검색 아이콘부터(기본; home/login/post/unknown)
#   tag     : 검색결과(explore)에서 태그 제안 클릭부터 (해시태그 모드)
#   grid    : 태그 그리드에서 게시물 수집부터 (검색 생략)
#   kw      : 검색결과(계정 목록)에서 프로필 클릭부터 (캡션 키워드 모드)
#   profile : 이미 프로필 페이지 → 현재 프로필 수집부터
def resume_entry(page: str, mode: str) -> str:
    page = (page or "").lower()
    if page == "tag":
        return "grid"
    if page == "explore":
        return "kw" if mode == "keyword" else "tag"
    if page == "profile":
        return "profile"
    return "search"


# ── JS 함수 본문(헬퍼) ──────────────────────────────────────────────────────────

_FIND_FN = """(function(){
    function __first(c){
        try {
            if (c.type === 'css') return document.querySelector(c.value);
            if (c.type === 'coord') {
                var p = String(c.value).split(',');
                return document.elementFromPoint(parseFloat(p[0]), parseFloat(p[1]));
            }
            var r = document.evaluate(c.value, document, null, 9, null);
            return r.singleNodeValue;
        } catch (e) { return null; }
    }
    function __findFirst(cands){
        for (var i = 0; i < cands.length; i++){ var el = __first(cands[i]); if (el) return el; }
        return null;
    }
    // 실제 마우스 클릭처럼 이벤트 시퀀스를 디스패치(React/IG 가 .click() 만으로는
    // 반응하지 않는 경우 대응). 좌표는 요소 중심으로 채운다.
    function __fire(el){
        try { el.scrollIntoView({block: 'center', inline: 'center'}); } catch (e) {}
        var r; try { r = el.getBoundingClientRect(); } catch (e) { r = {left:0, top:0, width:0, height:0}; }
        var cx = r.left + r.width / 2, cy = r.top + r.height / 2;
        var base = {bubbles: true, cancelable: true, view: window, clientX: cx, clientY: cy, button: 0};
        var seq = ['pointerover','pointerenter','pointerdown','mousedown',
                   'pointerup','mouseup','click'];
        for (var i = 0; i < seq.length; i++){
            var type = seq[i];
            try {
                var Ev = (type.indexOf('pointer') === 0 && window.PointerEvent) ? PointerEvent : MouseEvent;
                el.dispatchEvent(new Ev(type, base));
            } catch (e) {
                try { el.dispatchEvent(new MouseEvent(type.replace('pointer','mouse'), base)); } catch (e2) {}
            }
            if (type === 'mousedown') { try { el.focus(); } catch (e) {} }
        }
        try { el.click(); } catch (e) {}
    }
"""

_CLICK_FN = _FIND_FN + """
    function __tryClick(cands){
        for (var i = 0; i < cands.length; i++){
            var el = __first(cands[i]);
            if (el) {
                var tgt = (el.closest ? (el.closest('a,button,[role=link],[role=button],input') || el) : el);
                try { __fire(tgt); return i; } catch (e) {}
            }
        }
        return -1;
    }
"""

_CLICK_INDEX_FN = _FIND_FN + """
    function __nodes(c){
        try {
            if (c.type === 'css') return Array.prototype.slice.call(document.querySelectorAll(c.value));
            if (c.type === 'coord') return [];
            var r = document.evaluate(c.value, document, null, 7, null);
            var a = []; for (var i = 0; i < r.snapshotLength; i++) a.push(r.snapshotItem(i));
            return a;
        } catch (e) { return []; }
    }
    function __clickIndex(cands, idx){
        for (var i = 0; i < cands.length; i++){
            var ns = __nodes(cands[i]);
            if (ns.length > idx) {
                var el = ns[idx];
                var tgt = (el.closest ? (el.closest('a,button,[role=link],[role=button]') || el) : el);
                try { __fire(tgt); return true; } catch (e) {}
            }
        }
        return false;
    }
"""

_COUNT_FN = """(function(){
    function __count(cands){
        for (var i = 0; i < cands.length; i++){
            var c = cands[i];
            try {
                if (c.type === 'css') { var n = document.querySelectorAll(c.value).length; if (n) return n; }
                else if (c.type !== 'coord') {
                    var r = document.evaluate(c.value, document, null, 7, null);
                    if (r.snapshotLength) return r.snapshotLength;
                }
            } catch (e) {}
        }
        return 0;
    }
"""


# ── Engine ───────────────────────────────────────────────────────────────────

class EmbeddedScraper(QObject):
    """임베디드 브라우저에서 클릭 기반으로 수집하는 이벤트 구동 엔진.

    ScraperThread 와 동일한 신호를 노출해 main_window 배선을 재사용한다. QThread
    가 아니라 메인 스레드 이벤트 루프 위에서 runJavaScript 콜백 + QTimer 로 단계를
    진행한다(QtWebEngine 은 메인 스레드 전용)."""

    log_signal           = pyqtSignal(str)
    progress_signal      = pyqtSignal(int, int)
    result_signal        = pyqtSignal(dict)
    done_signal          = pyqtSignal()
    error_signal         = pyqtSignal(str)
    waiting_login_signal = pyqtSignal()
    login_ok_signal      = pyqtSignal()
    step_signal          = pyqtSignal(str)
    skip_signal          = pyqtSignal(str)
    blocked_signal       = pyqtSignal()

    def __init__(self, browser, *, mode="hashtag", search_term="", count=10,
                 min_followers=0, max_followers=0, excluded_set=None,
                 selectors=None, flow=None, target=None, **_ignored):
        super().__init__()
        self._browser = browser
        self.mode = mode
        self.search_term = search_term or ""
        self.count = int(count or 0)
        self.min_followers = int(min_followers or 0)
        self.max_followers = int(max_followers or 0)
        self._excluded = {(u or "").lstrip("@").lower() for u in (excluded_set or set())}

        from core import storage
        self._selectors = selectors if selectors is not None else storage.load_selectors()
        self._flow = flow if flow is not None else storage.load_flow()
        # 타겟 전용 필터(target.csv §2.5) — 팔로잉 범위 / 최소 게시물. 0 = 무제한.
        _t = target if target is not None else storage.load_target()
        self.min_following = int((_t or {}).get("min_following", 0) or 0)
        self.max_following = int((_t or {}).get("max_following", 0) or 0)
        self.min_posts = int((_t or {}).get("min_posts", 0) or 0)
        self._delays = storage.load_delays()
        self._skip_first = str(self._flow.get("skip_first_post", "true")).lower() == "true"
        self.posts_per_tag = int(self._flow.get("posts_per_tag", 5) or 5)

        self._running = False
        self._collected = 0
        self._seen: set[str] = set()
        self._keywords: list[str] = []
        self._kw_idx = 0
        self._post_idx = 0
        self._post_total = 0
        self._cur_keyword = ""

    # ── ScraperThread 호환 API (main_window 에서 호출) ───────────────────────────

    def isRunning(self) -> bool:
        return self._running

    def wait(self, ms: int = 0) -> bool:
        return True

    def login_done(self):
        pass

    def stop(self):
        self._running = False

    # ── 로깅/딜레이 ─────────────────────────────────────────────────────────────

    def _log(self, msg):
        self.log_signal.emit(msg)

    def _step(self, msg):
        self.step_signal.emit(msg)
        self._log(f"[step] {msg}")

    # 단계 간 딜레이 하한(초). typing_char(글자당)는 제외하고 모두 최소 하한 보장 —
    # 기존 delays.csv 값이 작아도 확실히 텀을 둔다. 캡쳐(screenshot)는 화면이 완전히
    # 그려진 뒤 찍히도록 더 높은 하한을 둔다.
    _MIN_DELAY_SEC = 1.5
    _MIN_DELAY_BY_KEY = {"screenshot": 3.5}

    def _rand_ms(self, key) -> int:
        import random
        lo, hi = self._delays.get(key, (1.5, 3.0))
        try:
            lo, hi = float(lo), float(hi)
        except (TypeError, ValueError):
            lo, hi = 1.5, 3.0
        if key != "typing_char":
            lo = max(lo, self._MIN_DELAY_BY_KEY.get(key, self._MIN_DELAY_SEC))
            hi = max(hi, lo + 0.5)
        if hi < lo:
            hi = lo
        try:
            return int(random.uniform(lo, hi) * 1000)
        except Exception:
            return 1500

    def _after(self, key, fn):
        """랜덤 딜레이 후 fn() 호출(중단되면 무시)."""
        delay = self._rand_ms(key)
        self._log(f"  [delay/{key}] {delay/1000:.1f}s")
        QTimer.singleShot(delay, lambda: fn() if self._running else None)

    # ── JS 실행/클릭 헬퍼 ───────────────────────────────────────────────────────

    def _js(self, script, cb):
        if not self._running:
            return
        try:
            self._browser.page().runJavaScript(script, cb)
        except Exception as exc:
            self.error_signal.emit(str(exc))
            self._finish()

    def _dismiss(self, cb):
        """모달 닫기 시도 후 cb()."""
        self._js(dismiss_popup_js(), lambda n: (
            self._log(f"  [popup] {n}개 닫음") if n else None, cb()
        )[-1])

    def _cands(self, step_id):
        return candidates_for(self._selectors, step_id)

    def _click(self, step_id, cb):
        """step_id 후보를 순서대로 클릭(coord 폴백 포함). cb(success: bool)."""
        cands = self._cands(step_id)
        if not cands:
            self._log(f"  [ERROR] {step_id} 후보 없음")
            cb(False)
            return
        self._js(build_click_js(cands), lambda idx: self._on_click(step_id, idx, cb))

    def _on_click(self, step_id, idx, cb):
        if isinstance(idx, int) and idx >= 0:
            kind = self._cands(step_id)[idx].get("type")
            self._log(f"  [click/{step_id}] 후보 {idx + 1} ({kind}) 클릭")
            cb(True)
        else:
            self._log(f"  [ERROR] [click/{step_id}] 모든 후보 실패")
            cb(False)

    # 요소가 로딩될 때까지 폴링 후 클릭(없다고 바로 넘어가지 않음).
    _WAIT_TRIES = 8     # 최대 재시도 횟수
    _WAIT_MS = 1500     # 재시도 간격(ms) → 최대 ~12초 대기

    def _sleep(self, ms, fn):
        QTimer.singleShot(int(ms), lambda: fn() if self._running else None)

    def _real_click_ready(self, step_id, cb):
        """요소가 나타날 때까지 기다린 뒤, **실제 Qt 마우스 클릭**(isTrusted)으로
        클릭한다. JS 합성 클릭이 안 먹는 검색창 등에 사용. real_click 미지원 시
        일반 _click_ready 로 폴백. cb(success)."""
        browser = self._browser
        if not hasattr(browser, "real_click_css"):
            return self._click_ready(step_id, cb)
        cands = self._cands(step_id)
        if not cands:
            self._log(f"  [ERROR] {step_id} 후보 없음")
            return cb(False)

        def attempt(left):
            self._js(build_count_js(cands), lambda n: on_count(int(n or 0), left))

        def on_count(n, left):
            if n > 0:
                self._js(build_rect_js(cands), on_rect)
            elif left > 0 and self._running:
                self._log(f"  [wait/{step_id}] 로딩 대기... ({self._WAIT_TRIES - left + 1}/{self._WAIT_TRIES})")
                self._sleep(self._WAIT_MS, lambda: attempt(left - 1))
            else:
                self._log(f"  [ERROR] [{step_id}] 요소 없음(대기 초과)")
                cb(False)

        def on_rect(rect):
            if isinstance(rect, dict) and rect.get("x") is not None:
                try:
                    self._browser.real_click_css(rect["x"], rect["y"])
                    self._log(f"  [realclick/{step_id}] ({rect['x']:.0f},{rect['y']:.0f}) 실제 클릭")
                    return cb(True)
                except Exception as exc:
                    self._log(f"  [realclick-err] {exc}")
            cb(False)

        attempt(self._WAIT_TRIES)

    def _click_ready(self, step_id, cb):
        """후보 요소가 나타날 때까지 기다렸다 클릭. coord 후보가 있으면 끝까지
        못 찾아도 좌표 클릭을 시도한다. cb(success)."""
        cands = self._cands(step_id)
        if not cands:
            self._log(f"  [ERROR] {step_id} 후보 없음")
            return cb(False)
        has_coord = any(c.get("type") == "coord" for c in cands)

        def attempt(left):
            self._js(build_count_js(cands), lambda n: on_count(int(n or 0), left))

        def on_count(n, left):
            if n > 0:
                self._js(build_click_js(cands), lambda idx: self._on_click(step_id, idx, cb))
            elif left > 0 and self._running:
                self._log(f"  [wait/{step_id}] 로딩 대기... ({self._WAIT_TRIES - left + 1}/{self._WAIT_TRIES})")
                self._sleep(self._WAIT_MS, lambda: attempt(left - 1))
            elif has_coord:
                self._log(f"  [wait/{step_id}] 셀렉터 실패 → 좌표 클릭 시도")
                self._js(build_click_js(cands), lambda idx: self._on_click(step_id, idx, cb))
            else:
                self._log(f"  [ERROR] [{step_id}] 요소 없음(대기 초과)")
                cb(False)

        attempt(self._WAIT_TRIES)

    def _click_index_ready(self, step_id, index, cb):
        """후보 매칭이 index 개 이상 될 때까지 기다렸다 index 번째 클릭. 결과가
        있으나 index 가 모자라면 0번째라도 클릭. cb(success)."""
        cands = self._cands(step_id)
        if not cands:
            self._log(f"  [ERROR] {step_id} 후보 없음")
            return cb(False)

        def attempt(left):
            self._js(build_count_js(cands), lambda n: on_count(int(n or 0), left))

        def on_count(n, left):
            if n > index:
                self._js(build_click_index_js(cands, index),
                         lambda ok: self._on_idx(step_id, ok, cb))
            elif n > 0:
                self._js(build_click_index_js(cands, 0),
                         lambda ok: self._on_idx(step_id, ok, cb))
            elif left > 0 and self._running:
                self._log(f"  [wait/{step_id}] 로딩 대기... ({self._WAIT_TRIES - left + 1}/{self._WAIT_TRIES})")
                self._sleep(self._WAIT_MS, lambda: attempt(left - 1))
            else:
                self._log(f"  [ERROR] [{step_id}] 결과 없음(대기 초과)")
                cb(False)

        attempt(self._WAIT_TRIES)

    def _on_idx(self, step_id, ok, cb):
        if ok:
            self._log(f"  [click/{step_id}] 클릭")
            cb(True)
        else:
            cb(False)

    # ── 수집 시작/종료 ──────────────────────────────────────────────────────────

    def start(self):
        from core import storage
        self._running = True
        self._collected = 0
        self._seen = set(storage.seen_usernames()) | self._excluded
        self._keywords = _parse_keywords(self.search_term)
        self._kw_idx = 0
        self._cur_keyword = self._keywords[0] if self._keywords else ""
        self._log("[browser] 임베디드 브라우저에서 수집을 시작합니다(클릭 방식).")
        self.login_ok_signal.emit()
        QTimer.singleShot(500, self._resume_or_start)

    def _resume_or_start(self):
        """현재 브라우저가 어느 페이지(=플로우 어디)에 있는지 확인하고 거기서부터
        시작한다('지금 위치 확인' 플로우). 라우팅 정책은 모듈의 resume_entry()."""
        if not self._running:
            return
        self._page_state(self._route_from_page)

    def _route_from_page(self, page):
        entry = resume_entry(page, self.mode)
        self._log(f"  [page] 현재 위치: {page} → 진입 단계: {entry}")
        if entry == "search" or not self._keywords:
            return self._next_keyword()
        # 검색을 건너뛰고 중간부터 시작 → 첫 키워드를 '소비한' 상태로 맞춘다.
        self._cur_keyword = self._keywords[0]
        self._kw_idx = 1
        if entry == "grid":
            self._grid_tries = 0
            return self._count_posts()
        if entry == "tag":
            return self._do_tag()
        if entry == "kw":
            return self._kw_start()
        if entry == "profile":
            return self._resume_profile()
        return self._next_keyword()

    def _resume_profile(self):
        """이미 프로필 페이지 → 현재 프로필을 수집한 뒤 다음 키워드로 진행."""
        self._step("현재 프로필 정보 수집(재개)")
        self._wait_profile(
            self._WAIT_TRIES,
            lambda data: self._save_info(parse_profile(data or {}), self._next_keyword),
        )

    def _finish(self):
        if not self._running:
            # 이미 종료 처리됨.
            self.done_signal.emit()
            return
        self._running = False
        self._log(f"[done] collected {self._collected} accounts")
        self.done_signal.emit()

    # ── 단계 흐름(키워드 → 검색 → 태그 → 게시물 → 프로필) ───────────────────────

    def _next_keyword(self):
        if not self._running or self._collected >= self.count:
            return self._finish()
        if self._kw_idx >= len(self._keywords):
            return self._finish()
        self._cur_keyword = self._keywords[self._kw_idx]
        self._kw_idx += 1
        self._step(f"검색 아이콘 클릭 (키워드 {self._kw_idx}/{len(self._keywords)})")
        self._dismiss(lambda: self._real_click_ready("search_icon", self._after_search_icon))

    def _after_search_icon(self, ok):
        if not ok:
            self._log("  [skip] 검색 아이콘 클릭 실패 → 다음 키워드")
            return self._after("step1", self._next_keyword)
        # 검색 아이콘 클릭 후, 검색창을 먼저 클릭해 활성화(포커스)해야 입력이
        # 인스타 검색에 반영된다(클릭 없이 값만 넣으면 검색이 안 됨).
        self._after("step1", self._click_search_box)

    def _click_search_box(self):
        self._step("검색창 클릭(활성화)")
        # 검색창은 JS 합성 클릭이 안 먹어(isTrusted=false) → 실제 Qt 마우스 클릭.
        # 전용 스텝 'search_box' 후보(없으면 search_input) 위치에 실제 클릭.
        step = "search_box" if self._cands("search_box") else "search_input"
        self._real_click_ready(step, self._after_click_box)

    def _after_click_box(self, ok):
        if not ok:
            self._log("  [warn] 검색창 클릭 실패 — 입력만으로 시도")
        # 클릭 성공/실패와 무관하게 잠시 후 입력(포커스가 잡혔을 수 있음).
        self._after("step2", self._do_type)

    def _do_type(self):
        # 해시태그 모드는 '#키워드', 캡션 키워드 모드는 '#' 없이 키워드만 입력.
        text = (f"#{self._cur_keyword}" if self.mode == "hashtag"
                else self._cur_keyword)
        self._step(f"검색어 입력: {text}")
        cands = self._cands("search_input")
        self._js(build_type_js(cands, text), lambda ok: self._after_type(ok))

    def _after_type(self, ok):
        if not ok:
            self._log("  [skip] 검색창 입력 실패 → 다음 키워드")
            return self._after("step2", self._next_keyword)
        if self.mode == "hashtag":
            # 해시태그: 태그 제안 클릭 → 게시물 그리드.
            self._after("step2", self._do_tag)
        else:
            # 캡션 키워드: 검색 결과가 계정 목록이고 클릭하면 바로 프로필.
            self._after("step2", self._kw_start)

    def _do_tag(self):
        self._step("태그 결과 클릭 (제안 로딩 대기)")
        # 검색 제안은 비동기 로딩 → 나타날 때까지 폴링 후 클릭(없다고 바로 안 넘어감).
        self._dismiss(lambda: self._click_index_ready("tag_result", 0, self._after_tag))

    def _after_tag(self, ok):
        if not ok:
            self._log("  [skip] 태그 결과 없음 → 다음 키워드")
            return self._after("step3", self._next_keyword)
        self._grid_tries = 0
        self._after("step3", self._count_posts)

    def _count_posts(self):
        self._step("게시물 그리드 로딩 확인")
        self._js(build_count_js(self._cands("post_link")), self._after_count)

    def _after_count(self, n):
        n = int(n or 0)
        threshold = 1 if self._skip_first else 0
        if n <= threshold:
            # 태그 클릭 직후 그리드가 아직 안 떴을 수 있음 → 스크롤/대기 후 재확인.
            self._grid_tries = getattr(self, "_grid_tries", 0) + 1
            if self._running and self._grid_tries <= 5:
                self._log(f"  [grid] 게시물 로딩 대기... ({self._grid_tries}/5)")
                self._js("window.scrollBy(0, 600); true",
                         lambda _ok: self._after("scroll", self._count_posts))
                return
            self._log("  [skip] 게시물 없음 → 다음 키워드")
            return self._next_keyword()
        self._post_total = n
        self._post_idx = threshold   # 첫 썸네일=본인 → 건너뜀
        self._log(f"  [grid] 게시물 {n}개 감지 → 이미지 클릭 시작")
        self._open_post()

    def _open_post(self):
        if not self._running or self._collected >= self.count:
            return self._finish()
        if self._post_idx >= self._post_total:
            return self._after("back", self._next_keyword)
        self._step(f"게시물 클릭 {self._post_idx + 1}/{self._post_total}")
        self._dismiss(lambda: self._js(
            build_click_index_js(self._cands("post_link"), self._post_idx),
            self._after_open_post,
        ))

    def _after_open_post(self, ok):
        if not ok:
            self._post_idx += 1
            return self._after("step4", self._open_post)
        self._after("step4", self._peek)

    _PEEK_TRIES = 4   # 작성자 링크가 늦게 뜰 수 있어 username 을 몇 번 재시도

    def _peek(self, left=None):
        if left is None:
            left = self._PEEK_TRIES
        self._js(_PEEK_USERNAME_JS, lambda u: self._on_peek(u, left))

    def _on_peek(self, username, left):
        # username 을 못 읽으면(게시물 로딩 지연) 잠깐 기다렸다 재시도 — 제외/기존
        # 계정을 프로필에 들어가기 전에 확실히 걸러내기 위함.
        norm = (username or "").lstrip("@").strip().lower() if username else ""
        if not norm and left > 0 and self._running:
            self._sleep(self._WAIT_MS, lambda: self._peek(left - 1))
            return
        self._after_peek(username)

    def _after_peek(self, username):
        norm = (username or "").lstrip("@").strip().lower() if username else ""
        # 제외 명단 / 이미 수집된 계정 → 프로필로 들어가지 않고 다음 이미지로.
        if norm and norm in self._seen:
            self.skip_signal.emit(norm)
            self._log(f"  [skip] 제외/중복 — 프로필 진입 안 함: @{norm}")
            self._post_idx += 1
            return self._go_back_to_listing(self._open_post)
        # 프로필 진입(이름 클릭)
        self._step("프로필 이름 클릭")
        self._click_ready("profile_link", self._after_profile_click)

    def _after_profile_click(self, ok):
        if not ok:
            self._log("  [skip] 프로필 링크 실패")
            self._post_idx += 1
            return self._go_back_to_listing(self._open_post)
        self._after("step5", self._extract)

    def _extract(self):
        self._step("프로필 정보 저장 (로딩 대기)")
        self._wait_profile(self._WAIT_TRIES, self._after_extract)

    def _wait_profile(self, left, cb):
        """프로필 헤더(팔로워/유저네임)가 로딩될 때까지 기다렸다 cb(data) 호출."""
        cands = self._cands("followers_count") + self._cands("username_text")
        self._js(build_count_js(cands), lambda n: self._on_profile_ready(int(n or 0), left, cb))

    def _on_profile_ready(self, n, left, cb):
        if n > 0 or left <= 0 or not self._running:
            self._js(build_profile_js(self._selectors), cb)
        else:
            self._log(f"  [wait/profile] 프로필 로딩 대기... ({self._WAIT_TRIES - left + 1}/{self._WAIT_TRIES})")
            self._sleep(self._WAIT_MS, lambda: self._wait_profile(left - 1, cb))

    def _capture_screenshot(self, username: str) -> str:
        """현재 브라우저 화면을 PNG로 캡처해 data/screenshots/{username}.png 저장 후 경로 반환."""
        from pathlib import Path
        from core import storage
        shots_dir = storage.DATA_DIR / "screenshots"
        shots_dir.mkdir(parents=True, exist_ok=True)
        path = shots_dir / f"{username}.png"
        try:
            pixmap = self._browser.grab()
            if not pixmap.isNull():
                pixmap.save(str(path), "PNG")
                return str(path)
        except Exception as exc:
            self._log(f"  [screenshot] 캡처 실패: {exc}")
        return ""

    def _target_reject_reason(self, info: dict) -> str:
        """타겟 범위(팔로워/팔로잉/게시물, target.csv §2.5)에 안 맞으면 사유 문자열,
        통과하면 빈 문자열. 0 인 한계는 '무제한'으로 무시한다."""
        f = parse_followers(info.get("followers", ""))
        if (self.min_followers > 0 and f < self.min_followers) or \
           (self.max_followers > 0 and f > self.max_followers):
            return f"팔로워 {f:,} 범위 밖"
        if self.min_following > 0 or self.max_following > 0:
            fw = parse_followers(info.get("following", ""))
            if (self.min_following > 0 and fw < self.min_following) or \
               (self.max_following > 0 and fw > self.max_following):
                return f"팔로잉 {fw:,} 범위 밖"
        if self.min_posts > 0:
            pc = parse_followers(info.get("posts_count", ""))
            if pc < self.min_posts:
                return f"게시물 {pc:,} 부족(<{self.min_posts:,})"
        return ""

    def _save_info(self, info, after_cb):
        """프로필 dedup/필터/저장 처리 후 after_cb() 로 다음 단계 진행.

        username 없음/중복/필터 탈락이면 저장 없이 after_cb. 두 모드(해시태그/
        캡션)가 공유하며, 복귀(뒤로가기) 방식만 after_cb 로 다르게 준다."""
        import datetime
        from core import storage
        if not info or not info.get("username"):
            self._log("  [skip] 유저네임 추출 실패")
            return after_cb()
        username = info["username"]
        norm = username.lower()
        if norm in self._seen:
            self.skip_signal.emit(username)
            self._log(f"  [skip] 중복: @{norm}")
            return after_cb()
        reason = self._target_reject_reason(info)
        if reason:
            self._log(f"  [filter] @{username} {reason}")
            self._seen.add(norm)
            return after_cb()
        self._seen.add(norm)
        # 캡처 전 대기 (설정 딜레이 탭 "screenshot" 항목)
        self._after("screenshot", lambda: self._do_capture_and_save(info, after_cb))

    def _do_capture_and_save(self, info, after_cb):
        """캡처 후 results.csv 에 저장하고 after_cb() 로 진행."""
        import datetime
        from core import storage
        username = info["username"]
        shot_path = self._capture_screenshot(username)
        if shot_path:
            info["screenshot_path"] = shot_path
        info["source_tag"] = self._cur_keyword
        info["collected_at"] = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
        try:
            appended = storage.append_result(info)
        except Exception as exc:
            self._log(f"  [save-err] {exc}")
            appended = False
        if appended:
            self._collected += 1
            self.result_signal.emit(info)
            self.progress_signal.emit(self._collected, self.count)
            self._log(f"[OK] @{username}  "
                      f"followers={info.get('followers', '?')}  "
                      f"[{self._collected}/{self.count}]")
        after_cb()

    def _after_extract(self, data):
        # 해시태그 모드: 저장 후 '목록(태그 그리드)'에 도달할 때까지 뒤로가기.
        info = parse_profile(data or {})
        self._post_idx += 1
        self._after("step6", lambda: self._save_info(
            info, lambda: self._go_back_to_listing(self._open_post)))

    # ── 현재 페이지 판별 / 페이지 기반 뒤로가기 ─────────────────────────────────

    def _page_state(self, cb):
        """현재 페이지 종류를 cb(state) 로 전달(login/tag/explore/post/home/profile)."""
        self._js(_PAGE_STATE_JS, lambda s: cb(s or "unknown"))

    def _go_back_to_listing(self, cb, left=4):
        """게시물/프로필 페이지면 목록(태그/탐색/홈)에 닿을 때까지 뒤로가기.

        고정 횟수 대신 현재 페이지를 확인하며 되돌아가, 인스타 네비게이션 차이에도
        정확히 목록으로 복귀한다(프로필→게시물→그리드 또는 프로필→검색결과)."""
        if not self._running:
            return cb()
        self._page_state(lambda pg: self._on_back_page(pg, cb, left))

    def _on_back_page(self, pg, cb, left):
        if pg in ("post", "profile") and left > 0:
            self._log(f"  [page] {pg} → 뒤로가기")
            self._do_one_back(lambda: self._sleep(400, lambda: self._go_back_to_listing(cb, left - 1)))
        else:
            self._log(f"  [page] 목록 도달({pg})")
            cb()

    # ── 캡션 키워드 모드(검색결과=계정 목록, 클릭하면 바로 프로필) ───────────────

    def _kw_start(self):
        self._kw_res_idx = 0
        self._after("step3", self._kw_open)

    def _kw_open(self):
        if not self._running or self._collected >= self.count:
            return self._finish()
        if self._kw_res_idx >= 12:   # 검색결과 최대 시도 수
            return self._after("back", self._next_keyword)
        self._step(f"검색결과 프로필 클릭 {self._kw_res_idx + 1}")
        self._dismiss(lambda: self._click_index_ready(
            "keyword_result", self._kw_res_idx, self._kw_after_click))

    def _kw_after_click(self, ok):
        if not ok:
            self._log("  [skip] 검색결과 없음 → 다음 키워드")
            return self._after("back", self._next_keyword)
        self._after("step5", self._kw_extract)

    def _kw_extract(self):
        self._step("프로필 정보 저장 (로딩 대기)")
        self._wait_profile(self._WAIT_TRIES, self._kw_after_extract)

    def _kw_after_extract(self, data):
        info = parse_profile(data or {})
        self._kw_res_idx += 1
        # 캡션 모드: 프로필 → '목록(검색결과)' 도달까지 뒤로가기.
        self._after("step6", lambda: self._save_info(
            info, lambda: self._go_back_to_listing(self._kw_open)))

    def _do_one_back(self, cb):
        """뒤로가기 1회(back_button 후보 클릭, 실패 시 history.back 폴백)."""
        cands = self._cands("back_button")

        def fallback(_ok=None):
            self._js("window.history.back(); true", lambda _o: self._after("back", cb))

        if cands:
            def on_idx(idx):
                if isinstance(idx, int) and idx >= 0:
                    self._after("back", cb)
                else:
                    fallback()
            self._js(build_click_js(cands), on_idx)
        else:
            fallback()


# parse_keywords 를 가볍게 재사용(steps.py 의존 회피용 로컬 구현).
def _parse_keywords(search_term):
    out, seen = [], set()
    for raw in re.split(r"[,\n]", search_term or ""):
        k = raw.strip().lstrip("#").strip()
        if k and k.lower() not in seen:
            seen.add(k.lower())
            out.append(k)
    return out or [""]
