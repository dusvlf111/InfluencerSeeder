"""Unit tests for embedded_scraper pure helpers (no QtWebEngine needed)."""

from core.embedded_scraper import (
    candidates_for, build_click_js, build_type_js, build_click_index_js,
    build_count_js, dismiss_popup_js, parse_profile, _num_for, _parse_keywords,
    build_profile_js, _clean_num,
)
from core.scraper_parsing import parse_followers


class TestCandidates:
    def test_groups_by_step_in_order(self):
        sels = [
            {"step_id": "search_icon", "selector_type": "css", "selector_value": "a"},
            {"step_id": "search_icon", "selector_type": "coord", "selector_value": "10,20"},
            {"step_id": "other", "selector_type": "xpath", "selector_value": "//x"},
        ]
        c = candidates_for(sels, "search_icon")
        assert c == [{"type": "css", "value": "a"}, {"type": "coord", "value": "10,20"}]

    def test_empty_when_no_match(self):
        assert candidates_for([], "x") == []


class TestJsBuilders:
    def test_click_js_contains_candidates_and_coord(self):
        js = build_click_js([{"type": "coord", "value": "1,2"}])
        assert "__tryClick" in js and "elementFromPoint" in js and "1,2" in js

    def test_type_js_has_react_setter(self):
        js = build_type_js([{"type": "css", "value": "input"}], "#hi")
        assert "HTMLInputElement" in js and "#hi" in js and "input" in js

    def test_click_index_js(self):
        js = build_click_index_js([{"type": "css", "value": "a"}], 3)
        assert "__clickIndex" in js and ", 3)" in js

    def test_count_js(self):
        assert "__count" in build_count_js([{"type": "css", "value": "a"}])

    def test_dismiss_js_lists_labels(self):
        js = dismiss_popup_js()
        # 검색 닫기 버튼을 누르지 않도록 '닫기/취소'는 제외, '나중에' 류만.
        assert "Not Now" in js and "나중에" in js and "닫기" not in js

    def test_profile_js_uses_field_selectors(self):
        sels = [{"step_id": "followers_count", "selector_type": "css",
                 "selector_value": "a[href*='/followers/'] span[title]"}]
        js = build_profile_js(sels)
        assert "followers" in js and "__findFirst" in js and "location.href" in js


class TestCleanNum:
    def test_extracts_first_number(self):
        assert _clean_num("팔로워 3,632명") == "3,632"

    def test_plain(self):
        assert _clean_num("3632") == "3632"

    def test_empty(self):
        assert _clean_num("") == "" and _clean_num("없음") == ""


class TestNumFor:
    def test_number_before_label_english(self):
        assert _num_for("3,632 Followers", "Followers|팔로워") == "3,632"

    def test_label_before_number_korean(self):
        assert _num_for("팔로워 3,632명", "Followers|팔로워") == "3,632"

    def test_comma_before_label_not_matched(self):
        # '...명, 팔로잉 10' — the comma must not be taken as the number.
        assert _num_for("팔로워 3,632명, 팔로잉 10명", "Following|팔로잉|팔로우") == "10"

    def test_missing_returns_empty(self):
        assert _num_for("no numbers here", "Posts|게시물") == ""


class TestParseProfile:
    def test_korean_meta(self):
        info = parse_profile({
            "url": "https://www.instagram.com/jakdang.code/",
            "meta": "팔로워 3,632명, 팔로잉 10명, 게시물 6개 - jakdang.code",
            "bio": "소개", "website": "http://x.com",
        })
        assert info["username"] == "jakdang.code"
        assert parse_followers(info["followers"]) == 3632
        assert info["following"] == "10"
        assert info["posts_count"] == "6"
        assert info["bio"] == "소개"
        assert info["website"] == "http://x.com"

    def test_english_meta(self):
        info = parse_profile({
            "url": "https://www.instagram.com/foo/",
            "meta": "3,632 Followers, 10 Following, 6 Posts - foo",
            "bio": "", "website": "",
        })
        assert info["username"] == "foo"
        assert info["followers"] == "3,632"

    def test_dom_field_based(self):
        # SPA 라 meta 가 없을 때, DOM 셀렉터 필드 텍스트로 채운다.
        info = parse_profile({
            "url": "https://www.instagram.com/jakdang.code/",
            "username": "jakdang.code",
            "followers": "3632", "following": "10", "posts_count": "6",
            "bio": "개발자", "website": "http://x.com",
        })
        assert info["followers"] == "3632"
        assert info["following"] == "10"
        assert info["posts_count"] == "6"
        assert info["website"] == "http://x.com"

    def test_field_text_with_label_cleaned(self):
        info = parse_profile({
            "url": "https://www.instagram.com/x/",
            "followers": "팔로워 3,632명",
        })
        assert info["followers"] == "3,632"

    def test_blacklisted_username_rejected(self):
        assert parse_profile({"url": "https://www.instagram.com/explore/"}) == {}

    def test_no_url_returns_empty(self):
        assert parse_profile({"url": ""}) == {}


class TestParseKeywords:
    def test_split_and_dedup(self):
        assert _parse_keywords("인턴, 취준생\n#개발, 인턴") == ["인턴", "취준생", "개발"]

    def test_empty_yields_single_blank(self):
        assert _parse_keywords("") == [""]
