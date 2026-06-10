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

# (step_id, (delay_min, delay_max)) per PRD §2.3
_DELAY_DEFAULTS: list[tuple[str, tuple[float, float]]] = [
    ("step1",       (1.0, 2.5)),
    ("step2",       (0.5, 1.5)),
    ("step3",       (2.0, 4.0)),
    ("step4",       (1.5, 3.0)),
    ("step5",       (2.0, 4.0)),
    ("step6",       (0.5, 1.5)),
    ("back",        (1.0, 2.5)),
    ("scroll",      (0.8, 2.0)),
    ("typing_char", (0.05, 0.18)),
]

# ── Selectors (§2.2) — step 당 priority 정렬 fallback 체인 ──────────────────────

_SELECTOR_DEFAULTS: list[dict] = [
    {
        "step_id": "search_icon", "step_name": "돋보기 클릭(Step1)", "priority": 1,
        "selector_type": "xpath",
        "selector_value": "//a[contains(@href,'/explore/')]//*[name()='svg' and @aria-label='검색']",
    },
    {
        "step_id": "search_icon", "step_name": "돋보기 클릭(Step1)", "priority": 2,
        "selector_type": "xpath",
        "selector_value": "//a[contains(@href,'/search')]",
    },
    {
        "step_id": "search_icon", "step_name": "돋보기 클릭(Step1)", "priority": 3,
        "selector_type": "css",
        "selector_value": "svg[aria-label='Search']",
    },
    {
        "step_id": "search_input", "step_name": "검색 입력(Step2)", "priority": 1,
        "selector_type": "xpath",
        "selector_value": "//input[@placeholder='검색']",
    },
    {
        "step_id": "search_input", "step_name": "검색 입력(Step2)", "priority": 2,
        "selector_type": "xpath",
        "selector_value": "//input[@placeholder='Search']",
    },
    {
        "step_id": "tag_result", "step_name": "태그 클릭(Step3)", "priority": 1,
        "selector_type": "xpath",
        "selector_value": "//a[contains(@href,'/explore/tags/')]",
    },
    {
        "step_id": "post_link", "step_name": "이미지 클릭(Step4)", "priority": 1,
        "selector_type": "xpath",
        "selector_value": "//a[contains(@href,'/p/')]",
    },
    {
        "step_id": "profile_link", "step_name": "프로필 클릭(Step5)", "priority": 1,
        "selector_type": "css",
        "selector_value": "header a[href]:not([href='/'])",
    },
    {
        "step_id": "username_text", "step_name": "유저네임", "priority": 1,
        "selector_type": "css",
        "selector_value": "header h2, header h1",
    },
    {
        "step_id": "followers_count", "step_name": "팔로워 수", "priority": 1,
        "selector_type": "xpath",
        "selector_value": "//a[contains(@href,'/followers/')]//span[@title]",
    },
    {
        "step_id": "following_count", "step_name": "팔로우 수", "priority": 1,
        "selector_type": "xpath",
        "selector_value": "//a[contains(@href,'/following/')]//span",
    },
    {
        "step_id": "posts_count", "step_name": "게시물 수", "priority": 1,
        "selector_type": "xpath",
        "selector_value": "//header//li[1]//span//span",
    },
    {
        "step_id": "bio_text", "step_name": "소개글", "priority": 1,
        "selector_type": "css",
        "selector_value": "header section > div:last-child",
    },
    {
        "step_id": "website_link", "step_name": "웹사이트", "priority": 1,
        "selector_type": "css",
        "selector_value": "header a[href*='http']:not([href*='instagram.com'])",
    },
]

# v3 프로필 중심 스키마 (§3.1)
_RESULTS_FIELDNAMES = [
    "username", "full_name", "followers", "following", "posts_count",
    "bio", "website", "is_private", "profile_url",
    "source_tag", "source_post_url", "collected_at",
]

_SELECTOR_FIELDNAMES = ["step_id", "step_name", "priority", "selector_type", "selector_value"]
