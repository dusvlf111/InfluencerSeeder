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
