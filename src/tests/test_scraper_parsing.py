"""parse_followers (pure helper, used by the embedded scraper)."""

import pytest

from core.scraper_parsing import parse_followers


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
