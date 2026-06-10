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
