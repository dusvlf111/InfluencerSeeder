import pytest
from unittest.mock import MagicMock, patch

from core.scraper import parse_followers, ScraperThread


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
