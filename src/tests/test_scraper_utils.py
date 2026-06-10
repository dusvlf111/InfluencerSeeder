import pytest
from unittest.mock import MagicMock, patch

from core.scraper import (
    parse_followers,
    ScraperThread,
    _build_chrome_options,
    _apply_stealth,
    _UA_POOL,
)


class TestParseFollowers:
    @pytest.mark.parametrize("text, expected", [
        ("1만",        10_000),
        ("3.5만",      35_000),
        ("12만",       120_000),
        ("1천",        1_000),
        ("2.5천",      2_500),
        ("1억",        100_000_000),
        ("1,234",      1_234),
        ("12000",      12_000),
        ("1,234,567",  1_234_567),
        ("",           0),
        (None,         0),
        ("abc",        0),
        ("0",          0),
    ])
    def test_parse(self, text, expected):
        assert parse_followers(text) == expected


class TestScraperThreadIsValidUsername:
    def test_valid_username(self):
        assert ScraperThread._is_valid_username("johndoe", {"instagram"}) is True

    def test_rejects_blacklisted(self):
        assert ScraperThread._is_valid_username("instagram", {"instagram"}) is False

    def test_rejects_too_short(self):
        assert ScraperThread._is_valid_username("a", set()) is False

    def test_rejects_official_suffix(self):
        assert ScraperThread._is_valid_username("brandofficial", set()) is False

    def test_case_insensitive_blacklist(self):
        assert ScraperThread._is_valid_username("Instagram", {"instagram"}) is False


class TestResolveSelector:
    def _make_thread(self, chains):
        t = ScraperThread.__new__(ScraperThread)
        t._selector_chains = chains
        t._log = lambda msg: None
        return t

    def test_priority1_match_returns_first_priority(self):
        chains = {
            "search_icon": [
                {"step_id": "search_icon", "priority": 1, "selector_type": "xpath", "selector_value": "//a"},
                {"step_id": "search_icon", "priority": 2, "selector_type": "css", "selector_value": "svg"},
            ]
        }
        t = self._make_thread(chains)
        el1 = MagicMock(name="el1")
        driver = MagicMock()
        driver.find_elements.return_value = [el1, MagicMock()]
        result = t._resolve_selector(driver, "search_icon")
        assert result is el1
        # priority1 matched -> only one find_elements call
        assert driver.find_elements.call_count == 1

    def test_priority1_empty_falls_back_to_priority2(self):
        chains = {
            "search_icon": [
                {"step_id": "search_icon", "priority": 1, "selector_type": "xpath", "selector_value": "//a"},
                {"step_id": "search_icon", "priority": 2, "selector_type": "css", "selector_value": "svg"},
            ]
        }
        t = self._make_thread(chains)
        el2 = MagicMock(name="el2")
        driver = MagicMock()
        driver.find_elements.side_effect = [[], [el2]]
        result = t._resolve_selector(driver, "search_icon")
        assert result is el2
        assert driver.find_elements.call_count == 2

    def test_all_fail_returns_none(self):
        chains = {
            "search_icon": [
                {"step_id": "search_icon", "priority": 1, "selector_type": "xpath", "selector_value": "//a"},
                {"step_id": "search_icon", "priority": 2, "selector_type": "css", "selector_value": "svg"},
            ]
        }
        t = self._make_thread(chains)
        driver = MagicMock()
        driver.find_elements.return_value = []
        assert t._resolve_selector(driver, "search_icon") is None

    def test_unknown_step_returns_none(self):
        t = self._make_thread({})
        assert t._resolve_selector(MagicMock(), "nope") is None

    def test_coord_type_parsed(self):
        chains = {
            "search_icon": [
                {"step_id": "search_icon", "priority": 1, "selector_type": "xpath", "selector_value": "//a"},
                {"step_id": "search_icon", "priority": 9, "selector_type": "coord", "selector_value": "120, 340"},
            ]
        }
        t = self._make_thread(chains)
        driver = MagicMock()
        driver.find_elements.return_value = []  # xpath fails -> coord fallback
        result = t._resolve_selector(driver, "search_icon")
        assert result == ("coord", (120.0, 340.0))

    def test_invalid_coord_skipped(self):
        chains = {
            "x": [
                {"step_id": "x", "priority": 1, "selector_type": "coord", "selector_value": "bad"},
            ]
        }
        t = self._make_thread(chains)
        assert t._resolve_selector(MagicMock(), "x") is None

    def test_build_selector_chains_sorts_by_priority(self):
        rows = [
            {"step_id": "a", "priority": 3, "selector_type": "xpath", "selector_value": "z"},
            {"step_id": "a", "priority": 1, "selector_type": "xpath", "selector_value": "x"},
            {"step_id": "a", "priority": 2, "selector_type": "xpath", "selector_value": "y"},
            {"step_id": "b", "priority": 1, "selector_type": "css", "selector_value": "q"},
        ]
        chains = ScraperThread._build_selector_chains(rows)
        assert [r["selector_value"] for r in chains["a"]] == ["x", "y", "z"]
        assert [r["selector_value"] for r in chains["b"]] == ["q"]


class TestStealth:
    @staticmethod
    def _args(options):
        return options.arguments

    def test_headless_added_when_true(self):
        opts = _build_chrome_options({"headless": "true"})
        assert "--headless=new" in self._args(opts)

    def test_headless_absent_when_false(self):
        opts = _build_chrome_options({"headless": "false"})
        assert "--headless=new" not in self._args(opts)

    def test_user_agent_added_when_randomize(self):
        with patch("core.scraper.random.choice", return_value=_UA_POOL[0]):
            opts = _build_chrome_options({"randomize_user_agent": "true"})
        assert any(a.startswith("--user-agent=") for a in self._args(opts))
        assert f"--user-agent={_UA_POOL[0]}" in self._args(opts)

    def test_user_agent_absent_when_off(self):
        opts = _build_chrome_options({"randomize_user_agent": "false"})
        assert not any(a.startswith("--user-agent=") for a in self._args(opts))

    def test_randomize_window_uses_preset(self):
        with patch("core.scraper.random.choice", return_value=(1366, 768)):
            opts = _build_chrome_options({"randomize_window": "true"})
        assert "--window-size=1366,768" in self._args(opts)

    def test_fixed_window_when_not_randomized(self):
        opts = _build_chrome_options({
            "randomize_window": "false",
            "window_width": 1280,
            "window_height": 900,
        })
        assert "--window-size=1280,900" in self._args(opts)

    def test_zero_window_randomizes(self):
        with patch("core.scraper.random.choice", return_value=(1440, 900)):
            opts = _build_chrome_options({
                "randomize_window": "false",
                "window_width": 0,
                "window_height": 0,
            })
        assert "--window-size=1440,900" in self._args(opts)

    def test_user_data_dir_added(self):
        opts = _build_chrome_options({"user_data_dir": "/tmp/profile"})
        assert "--user-data-dir=/tmp/profile" in self._args(opts)

    def test_automation_flag_always_present(self):
        opts = _build_chrome_options({})
        assert "--disable-blink-features=AutomationControlled" in self._args(opts)

    def test_apply_stealth_injects_script(self):
        driver = MagicMock()
        _apply_stealth(driver)
        assert driver.execute_script.called
        joined = " ".join(str(c) for c in driver.execute_script.call_args_list)
        assert "navigator" in joined and "webdriver" in joined


class TestHumanType:
    def _make_thread(self, typing=(0.05, 0.18)):
        t = ScraperThread.__new__(ScraperThread)
        t._delays = {"typing_char": typing}
        return t

    def test_send_keys_called_per_char(self):
        t = self._make_thread()
        el = MagicMock()
        with patch("core.scraper.time.sleep"), \
             patch("core.scraper.random.uniform", return_value=0.1):
            t._human_type(el, "#abc")
        assert el.send_keys.call_count == len("#abc")

    def test_sleep_called_per_char(self):
        t = self._make_thread()
        el = MagicMock()
        with patch("core.scraper.time.sleep") as sleep, \
             patch("core.scraper.random.uniform", return_value=0.1):
            t._human_type(el, "hello")
        assert sleep.call_count == len("hello")

    def test_empty_string_no_calls(self):
        t = self._make_thread()
        el = MagicMock()
        with patch("core.scraper.time.sleep") as sleep:
            t._human_type(el, "")
        assert el.send_keys.call_count == 0
        assert sleep.call_count == 0

    def test_uses_delays_range(self):
        t = self._make_thread(typing=(0.2, 0.4))
        el = MagicMock()
        with patch("core.scraper.time.sleep"), \
             patch("core.scraper.random.uniform", return_value=0.3) as uni:
            t._human_type(el, "ab")
        uni.assert_called_with(0.2, 0.4)


class TestShouldSkip:
    def _make_thread(self, seen):
        t = ScraperThread.__new__(ScraperThread)
        t._seen = set(seen)
        t._log = lambda msg: None
        t.skip_signal = MagicMock()
        return t

    def test_seen_username_skipped(self):
        t = self._make_thread({"abc"})
        assert t._should_skip("abc") is True
        t.skip_signal.emit.assert_called_once_with("abc")

    def test_unseen_username_not_skipped(self):
        t = self._make_thread({"abc"})
        assert t._should_skip("xyz") is False
        t.skip_signal.emit.assert_not_called()

    def test_case_and_at_normalization(self):
        t = self._make_thread({"abc"})
        assert t._should_skip("@ABC") is True

    def test_filter_failed_added_then_skipped(self):
        t = self._make_thread(set())
        assert t._should_skip("newuser") is False
        # caller marks filter-failed username as seen
        t._seen.add(t._norm_username("newuser"))
        assert t._should_skip("NewUser") is True

    def test_empty_username_not_skipped(self):
        t = self._make_thread({"abc"})
        assert t._should_skip("") is False


class TestResumeAndState:
    @pytest.fixture(autouse=True)
    def _isolate_storage(self, tmp_path, monkeypatch):
        from core import storage
        monkeypatch.setattr(storage, "DATA_DIR", tmp_path)

    def _kwargs(self, **over):
        base = dict(
            mode="hashtag",
            search_term="인턴",
            count=10,
            min_followers=0,
            max_followers=0,
            excluded_set=set(),
            web={"headless": "false"},
            delays={"typing_char": (0.05, 0.1), "step1": (1.0, 2.0)},
            flow={
                "max_tags": 5,
                "posts_per_tag": 7,
                "scroll_max_attempts": 9,
                "tag_start_index": 2,
                "stop_on_consecutive_miss": 4,
                "skip_visited_profile": "true",
            },
            target={
                "min_followers": 1000,
                "max_followers": 50000,
                "min_following": 10,
                "max_following": 200,
                "min_posts": 5,
            },
        )
        base.update(over)
        return base

    def test_config_groups_mapped(self):
        t = ScraperThread(**self._kwargs())
        assert t.max_tags == 5
        assert t.posts_per_tag == 7
        assert t.scroll_max_attempts == 9
        assert t.tag_start_index == 2
        assert t.stop_on_consecutive_miss == 4
        assert t.skip_visited_profile is True
        # min/max_followers were 0 -> pulled from target
        assert t.min_followers == 1000
        assert t.max_followers == 50000
        assert t.min_following == 10
        assert t.max_following == 200
        assert t.min_posts == 5

    def test_delays_attached(self):
        t = ScraperThread(**self._kwargs())
        assert t._delays["typing_char"] == (0.05, 0.1)

    def test_no_resume_defaults(self):
        t = ScraperThread(**self._kwargs())
        assert t._start_tag_index == 2  # from tag_start_index
        assert t._start_post_index == 0
        assert t._collected == 0
        assert t._seen == set()

    def test_resume_state_loaded(self):
        t = ScraperThread(**self._kwargs(resume_state={
            "tag_index": 3,
            "post_index": 4,
            "collected_count": 12,
            "seen_usernames": ["Abc", "@DEF"],
        }))
        assert t._start_tag_index == 3
        assert t._start_post_index == 4
        assert t._collected == 12
        assert t._seen == {"abc", "def"}

    def test_save_state_calls_storage(self):
        t = ScraperThread(**self._kwargs())
        t._seen = {"abc", "def"}
        t._collected = 7
        with patch("core.storage.save_state") as save:
            t._save_state(tag_index=2, post_index=3)
        assert save.call_count == 1
        payload = save.call_args[0][0]
        assert payload["keyword"] == "인턴"
        assert payload["tag_index"] == 2
        assert payload["post_index"] == 3
        assert payload["collected_count"] == 7
        assert sorted(payload["seen_usernames"]) == ["abc", "def"]
        assert "updated_at" in payload

    def test_explicit_followers_not_overridden_by_target(self):
        t = ScraperThread(**self._kwargs(min_followers=3000, max_followers=4000))
        assert t.min_followers == 3000
        assert t.max_followers == 4000


class TestBlockedDetection:
    def _make_thread(self):
        t = ScraperThread.__new__(ScraperThread)
        t._log = lambda msg: None
        return t

    @pytest.mark.parametrize("url", [
        "https://www.instagram.com/accounts/login/?next=/",
        "https://www.instagram.com/challenge/?next=/",
        "https://www.instagram.com/accounts/suspended/",
        "https://www.instagram.com/ACCOUNTS/LOGIN/",
    ])
    def test_blocked_urls(self, url):
        t = self._make_thread()
        driver = MagicMock()
        driver.current_url = url
        assert t._is_blocked(driver) is True

    @pytest.mark.parametrize("url", [
        "https://www.instagram.com/someuser/",
        "https://www.instagram.com/explore/tags/intern/",
        "https://www.instagram.com/p/abc123/",
        "https://www.instagram.com/",
    ])
    def test_normal_urls(self, url):
        t = self._make_thread()
        driver = MagicMock()
        driver.current_url = url
        assert t._is_blocked(driver) is False

    def test_current_url_exception_returns_false(self):
        t = self._make_thread()
        driver = MagicMock()
        type(driver).current_url = property(lambda self: (_ for _ in ()).throw(RuntimeError()))
        assert t._is_blocked(driver) is False


class TestScraperThreadPassesFollowerFilter:
    def _make_thread(self, min_f=0, max_f=0):
        t = ScraperThread.__new__(ScraperThread)
        t.min_followers = min_f
        t.max_followers = max_f
        t._log = lambda msg: None
        return t

    def test_no_filter_always_passes(self):
        t = self._make_thread()
        ok, _ = t._passes_follower_filter(MagicMock(), "user")
        assert ok is True

    def test_max_filter_blocks_large_account(self):
        t = self._make_thread(max_f=10_000)
        with patch("core.scraper.get_follower_count", return_value="5만"):
            ok, _ = t._passes_follower_filter(MagicMock(), "user")
        assert ok is False

    def test_max_filter_passes_small_account(self):
        t = self._make_thread(max_f=10_000)
        with patch("core.scraper.get_follower_count", return_value="5천"):
            ok, _ = t._passes_follower_filter(MagicMock(), "user")
        assert ok is True

    def test_min_filter_blocks_small_account(self):
        t = self._make_thread(min_f=5_000)
        with patch("core.scraper.get_follower_count", return_value="1천"):
            ok, _ = t._passes_follower_filter(MagicMock(), "user")
        assert ok is False

    def test_range_filter_blocks_outside(self):
        t = self._make_thread(min_f=1_000, max_f=10_000)
        with patch("core.scraper.get_follower_count", return_value="5만"):
            ok, _ = t._passes_follower_filter(MagicMock(), "user")
        assert ok is False

    def test_range_filter_passes_inside(self):
        t = self._make_thread(min_f=1_000, max_f=10_000)
        with patch("core.scraper.get_follower_count", return_value="5천"):
            ok, _ = t._passes_follower_filter(MagicMock(), "user")
        assert ok is True
