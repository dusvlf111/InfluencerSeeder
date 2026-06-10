"""Pure default data for storage modules (no DATA_DIR / file I/O dependency).

Shared by ``core.storage`` (facade) and its sibling modules
(``storage_config`` / ``storage_selectors`` / ``storage_results`` / ``storage_state``).
"""

_SETTINGS_DEFAULTS: list[tuple[str, str]] = [
    ("min_followers",   "0"),
    ("max_followers",   "0"),
    ("posts_per_tag",   "5"),
    ("max_tags",        "3"),
    ("step1_delay_min", "1.0"),
    ("step1_delay_max", "2.5"),
    ("step2_delay_min", "0.5"),
    ("step2_delay_max", "1.5"),
    ("step3_delay_min", "2.0"),
    ("step3_delay_max", "4.0"),
    ("step4_delay_min", "1.5"),
    ("step4_delay_max", "3.0"),
    ("step5_delay_min", "2.0"),
    ("step5_delay_max", "4.0"),
    ("step6_delay_min", "0.5"),
    ("step6_delay_max", "1.5"),
    ("back_delay_min",  "1.0"),
    ("back_delay_max",  "2.5"),
]

# ── v3 setting group defaults (§2) ─────────────────────────────────────────────

_WEB_DEFAULTS: list[tuple[str, str]] = [
    ("browser",              "chrome"),
    ("headless",             "false"),
    ("window_width",         "1280"),
    ("window_height",        "900"),
    ("randomize_window",     "true"),
    ("randomize_user_agent", "true"),
    # iPhone 12 Pro 모바일 디바이스 에뮬레이션(390x844, DPR3, iOS Safari UA).
    ("mobile_ua",            "true"),
    ("user_data_dir",        ""),
    ("locale",               "ko-KR"),
    ("implicit_wait",        "5"),
    ("page_load_timeout",    "30"),
]

_FLOW_DEFAULTS: list[tuple[str, str]] = [
    ("max_tags",                 "3"),
    ("tag_start_index",          "0"),
    ("posts_per_tag",            "5"),
    ("scroll_max_attempts",      "15"),
    ("skip_visited_profile",     "true"),
    ("stop_on_consecutive_miss", "10"),
    # 태그 검색 결과의 첫 썸네일은 본인 프로필이라 게시물이 아님 → 건너뜀.
    ("skip_first_post",          "true"),
]

_TARGET_DEFAULTS: list[tuple[str, str]] = [
    ("min_followers", "0"),
    ("max_followers", "0"),
    ("min_following", "0"),
    ("max_following", "0"),
    ("min_posts",     "0"),
    ("keyword",       ""),
    ("mode",          "hashtag"),
]

# ── Collectable profile fields (Fix-2 B) ───────────────────────────────────────
#
# Which profile fields to extract/save. ``username`` is always collected (not a
# toggle). Each selectable field defaults to ``true``. ExtractProfile honors these
# (inactive fields are neither extracted nor saved → blank columns).

COLLECT_FIELDS: list[str] = [
    "full_name", "followers", "following", "posts_count", "bio", "website", "is_private",
]

_FIELDS_DEFAULTS: list[tuple[str, str]] = [(f, "true") for f in COLLECT_FIELDS]

# (step_id, (delay_min, delay_max)) per PRD §2.3
_DELAY_DEFAULTS: list[tuple[str, tuple[float, float]]] = [
    # 전체적으로 1초 이상 + 넉넉하게(봇 탐지 회피·로딩 대기). typing_char 만 글자당.
    ("step1",       (1.5, 3.0)),
    ("step2",       (1.5, 3.0)),
    ("step3",       (2.5, 5.0)),
    ("step4",       (2.0, 4.0)),
    ("step5",       (2.5, 5.0)),
    ("step6",       (1.5, 3.0)),
    ("back",        (1.5, 3.0)),
    ("scroll",      (1.0, 2.5)),
    ("typing_char", (0.10, 0.30)),
]

# ── Selectors (§2.2) — step 당 priority 정렬 fallback 체인 ──────────────────────

# 후보값은 실제 모바일 인스타 DOM(.claude/tasks/버튼맵핑.md) 기준으로, step 당
# 여러 개를 두어 위→아래 순서로 시도한다(하나 실패 시 다음). 세션마다 바뀌는
# 자동생성 클래스/mount id 는 쓰지 않고 안정적인 속성(href/placeholder/aria-label)만 사용.
_SELECTOR_DEFAULTS: list[dict] = [
    # ── 검색/탐색 아이콘 (Step1) ─────────────────────────────────────────────
    {
        "step_id": "search_icon", "step_name": "돋보기 클릭(Step1)", "priority": 1,
        "selector_type": "css",
        "selector_value": "svg[aria-label='검색'], svg[aria-label='Search']",
    },
    {
        "step_id": "search_icon", "step_name": "돋보기 클릭(Step1)", "priority": 2,
        "selector_type": "xpath",
        "selector_value": "//a[contains(@href,'/explore/')]",
    },
    {
        "step_id": "search_icon", "step_name": "돋보기 클릭(Step1)", "priority": 3,
        "selector_type": "css",
        "selector_value": "a[href*='/explore/'], a[href*='/search']",
    },

    # ── 검색창 클릭 (활성화) — 입력 전에 검색창을 클릭해 포커스 ───────────────
    {
        "step_id": "search_box", "step_name": "검색창 클릭", "priority": 1,
        "selector_type": "css",
        "selector_value": "input[type='search']",
    },
    {
        "step_id": "search_box", "step_name": "검색창 클릭", "priority": 2,
        "selector_type": "xpath",
        "selector_value": "//input[@placeholder='검색' or @placeholder='Search']",
    },
    {
        "step_id": "search_box", "step_name": "검색창 클릭", "priority": 3,
        "selector_type": "css",
        "selector_value": "input[placeholder], input[type='text']",
    },

    # ── 검색 입력 (Step2) — 실제: <input type="search" placeholder="검색"> ────
    {
        "step_id": "search_input", "step_name": "검색 입력(Step2)", "priority": 1,
        "selector_type": "css",
        "selector_value": "input[type='search']",
    },
    {
        "step_id": "search_input", "step_name": "검색 입력(Step2)", "priority": 2,
        "selector_type": "xpath",
        "selector_value": "//input[@placeholder='검색' or @placeholder='Search']",
    },
    {
        "step_id": "search_input", "step_name": "검색 입력(Step2)", "priority": 3,
        "selector_type": "css",
        "selector_value": "input[placeholder], input[type='text']",
    },

    # ── 태그 결과 클릭 (Step3) — 검색 제안의 태그 링크 ────────────────────────
    {
        "step_id": "tag_result", "step_name": "태그 클릭(Step3)", "priority": 1,
        "selector_type": "xpath",
        "selector_value": "//a[contains(@href,'/explore/tags/')]",
    },
    {
        "step_id": "tag_result", "step_name": "태그 클릭(Step3)", "priority": 2,
        "selector_type": "css",
        "selector_value": "a[href*='/explore/tags/']",
    },

    # ── 캡션 키워드 검색결과(계정) 클릭 — 클릭 시 바로 프로필로 이동 ──────────
    {
        "step_id": "keyword_result", "step_name": "검색결과(계정) 클릭", "priority": 1,
        "selector_type": "xpath",
        "selector_value": "//a[@role='link' and starts-with(@href,'/') and not(contains(@href,'/explore/')) and not(contains(@href,'/p/')) and not(contains(@href,'/reel/')) and string-length(@href)>2]",
    },
    {
        "step_id": "keyword_result", "step_name": "검색결과(계정) 클릭", "priority": 2,
        "selector_type": "css",
        "selector_value": "a[role='link'][href^='/']:not([href='/'])",
    },

    # ── 게시물 링크 (Step4) — 그리드 썸네일 ──────────────────────────────────
    {
        "step_id": "post_link", "step_name": "이미지 클릭(Step4)", "priority": 1,
        "selector_type": "xpath",
        "selector_value": "//a[contains(@href,'/p/') or contains(@href,'/reel/')]",
    },
    {
        "step_id": "post_link", "step_name": "이미지 클릭(Step4)", "priority": 2,
        "selector_type": "css",
        "selector_value": "a[href*='/p/'], a[href*='/reel/']",
    },

    # ── 프로필 링크 (Step5) — 게시물 상단 유저명 링크 ─────────────────────────
    {
        "step_id": "profile_link", "step_name": "프로필 클릭(Step5)", "priority": 1,
        "selector_type": "css",
        "selector_value": "article header a[href]:not([href='/'])",
    },
    {
        "step_id": "profile_link", "step_name": "프로필 클릭(Step5)", "priority": 2,
        "selector_type": "css",
        "selector_value": "header a[href]:not([href='/'])",
    },
    {
        "step_id": "profile_link", "step_name": "프로필 클릭(Step5)", "priority": 3,
        "selector_type": "css",
        "selector_value": "a[href]:not([href='/']):not([href*='/p/']):not([href*='/explore/']):not([href*='/reel/'])",
    },

    # ── 프로필 페이지: 유저네임 (header h2/h1) ───────────────────────────────
    {
        "step_id": "username_text", "step_name": "유저네임", "priority": 1,
        "selector_type": "css",
        "selector_value": "header h2, header h1",
    },
    {
        "step_id": "username_text", "step_name": "유저네임", "priority": 2,
        "selector_type": "css",
        "selector_value": "h2, h1",
    },

    # ── 팔로워 수 — 실제: a[href*='/followers/'] 안의 span[title] ────────────
    {
        "step_id": "followers_count", "step_name": "팔로워 수", "priority": 1,
        "selector_type": "xpath",
        "selector_value": "//a[contains(@href,'/followers/')]//span[@title]",
    },
    {
        "step_id": "followers_count", "step_name": "팔로워 수", "priority": 2,
        "selector_type": "css",
        "selector_value": "a[href*='/followers/'] span[title]",
    },
    {
        "step_id": "followers_count", "step_name": "팔로워 수", "priority": 3,
        "selector_type": "xpath",
        "selector_value": "//a[contains(@href,'/followers/')]//span",
    },

    # ── 팔로우 수 ────────────────────────────────────────────────────────────
    {
        "step_id": "following_count", "step_name": "팔로우 수", "priority": 1,
        "selector_type": "css",
        "selector_value": "a[href*='/following/'] span[title]",
    },
    {
        "step_id": "following_count", "step_name": "팔로우 수", "priority": 2,
        "selector_type": "xpath",
        "selector_value": "//a[contains(@href,'/following/')]//span",
    },

    # ── 게시물 수 — 실제 모바일: "게시물 <span><span>N</span></span>" ────────
    {
        "step_id": "posts_count", "step_name": "게시물 수", "priority": 1,
        "selector_type": "xpath",
        "selector_value": "//span[contains(.,'게시물') or contains(.,'Posts')]//span/span",
    },
    {
        "step_id": "posts_count", "step_name": "게시물 수", "priority": 2,
        "selector_type": "xpath",
        "selector_value": "//header//li[1]//span//span",
    },

    # ── 소개글 / 웹사이트 ────────────────────────────────────────────────────
    {
        "step_id": "bio_text", "step_name": "소개글", "priority": 1,
        "selector_type": "css",
        "selector_value": "header section > div:last-child, header div[dir]",
    },
    {
        "step_id": "website_link", "step_name": "웹사이트", "priority": 1,
        "selector_type": "css",
        "selector_value": "header a[href*='http']:not([href*='instagram.com'])",
    },

    # ── 뒤로가기 버튼 — 실제: svg[aria-label='돌아가기'] (go_back 폴백용) ──────
    {
        "step_id": "back_button", "step_name": "뒤로가기", "priority": 1,
        "selector_type": "css",
        "selector_value": "svg[aria-label='돌아가기'], svg[aria-label='Back']",
    },
]

# v3 프로필 중심 스키마 (§3.1)
_RESULTS_FIELDNAMES = [
    "username", "full_name", "followers", "following", "posts_count",
    "bio", "website", "is_private", "profile_url",
    "source_tag", "source_post_url", "collected_at",
]

_SELECTOR_FIELDNAMES = ["step_id", "step_name", "priority", "selector_type", "selector_value"]

# ── Flow steps (260610-4) — 순서 있는 데이터 기반 액션 시퀀스 ────────────────────
#
# A flow is an ordered list of steps the engine interprets at run time. Each step
# names an ``action`` (fixed vocabulary below), an optional ``selector_ref``
# (a selectors.csv ``step_id`` whose priority chain locates the element), and an
# optional ``param`` template (``#{keyword}`` / ``{tag_index}`` / ``{posts_per_tag}``
# / a delay key). ``phase`` controls where the step runs in the tag/post loops.

# Fixed action vocabulary (UI dropdown + load-time validation + flow registry).
FLOW_ACTIONS: list[str] = [
    "open_home",        # navigate to instagram home if not already there
    "click",            # click the element resolved from selector_ref (coord fallback)
    "type",             # human-type ``param`` into the resolved input
    "click_index",      # click the Nth (param) matched element of selector_ref
    "collect_open",     # collect post URLs (selector_ref) → drives the per_post loop
    "peek_gate",        # early dedup gate (§6) — may SKIP_POST
    "navigate_profile", # open the profile linked from the current post
    "extract",          # extract profile fields into the result
    "filter",           # apply target.csv follower-range filter — may SKIP_POST
    "save",             # dedup + append result + emit signals + persist state
    "go_back",          # return to the tag grid (or browser back)
    "scroll",           # random scroll on the current page
    "wait",             # random delay (param = delay key)
]

# phase: pre_loop (once per run) | per_tag (each tag) | per_post (each post).
_FLOW_STEPS_FIELDNAMES = [
    "order", "phase", "step_name", "action", "selector_ref", "param", "enabled",
]

# Default flow == the proven 6-step hashtag pipeline (behavior-preserving).
_FLOW_STEPS_DEFAULTS: list[dict] = [
    {"order": 1,  "phase": "per_tag",  "step_name": "돋보기 클릭",     "action": "click",            "selector_ref": "search_icon",  "param": "",                "enabled": True},
    {"order": 2,  "phase": "per_tag",  "step_name": "검색 입력",       "action": "type",             "selector_ref": "search_input", "param": "#{keyword}",      "enabled": True},
    {"order": 3,  "phase": "per_tag",  "step_name": "태그 클릭",       "action": "click_index",      "selector_ref": "tag_result",   "param": "{tag_index}",     "enabled": True},
    {"order": 4,  "phase": "per_tag",  "step_name": "게시물 URL 수집", "action": "collect_open",     "selector_ref": "post_link",    "param": "{posts_per_tag}", "enabled": True},
    {"order": 5,  "phase": "per_post", "step_name": "중복 조기판정",   "action": "peek_gate",        "selector_ref": "profile_link", "param": "",                "enabled": True},
    {"order": 6,  "phase": "per_post", "step_name": "프로필 이동",     "action": "navigate_profile", "selector_ref": "profile_link", "param": "",                "enabled": True},
    {"order": 7,  "phase": "per_post", "step_name": "정보 추출",       "action": "extract",          "selector_ref": "",             "param": "",                "enabled": True},
    {"order": 8,  "phase": "per_post", "step_name": "필터",            "action": "filter",           "selector_ref": "",             "param": "",                "enabled": True},
    {"order": 9,  "phase": "per_post", "step_name": "저장",            "action": "save",             "selector_ref": "",             "param": "",                "enabled": True},
    {"order": 10, "phase": "per_post", "step_name": "뒤로가기",        "action": "go_back",          "selector_ref": "",             "param": "",                "enabled": True},
]
