"""Unit tests for the intercepted-click fallback (robust_click)."""

from unittest.mock import MagicMock

from core.flows.steps import robust_click


def _thread():
    t = MagicMock()
    t._log = MagicMock()
    return t


class TestRobustClick:
    def test_direct_click_succeeds(self):
        driver, t, el = MagicMock(), _thread(), MagicMock()
        assert robust_click(driver, t, el) is True
        el.click.assert_called_once()
        driver.execute_script.assert_not_called()

    def test_falls_back_to_scroll_then_click(self):
        driver, t = MagicMock(), _thread()
        el = MagicMock()
        # First click raises (intercepted), second (after scrollIntoView) works.
        el.click.side_effect = [Exception("intercepted"), None]
        assert robust_click(driver, t, el) is True
        assert el.click.call_count == 2
        # scrollIntoView was invoked once before the retry click.
        assert driver.execute_script.call_count == 1

    def test_falls_back_to_js_click(self):
        driver, t = MagicMock(), _thread()
        el = MagicMock()
        el.click.side_effect = Exception("intercepted")  # always intercepted
        assert robust_click(driver, t, el) is True
        # scrollIntoView + JS click → execute_script called twice.
        assert driver.execute_script.call_count == 2

    def test_returns_false_when_all_fail(self):
        driver, t = MagicMock(), _thread()
        el = MagicMock()
        el.click.side_effect = Exception("intercepted")
        driver.execute_script.side_effect = Exception("js blew up")
        assert robust_click(driver, t, el) is False
