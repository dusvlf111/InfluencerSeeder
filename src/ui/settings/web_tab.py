"""Web 탭 (§2.1) Mixin — _build_web_tab / _populate_web / _collect_web."""

from PyQt6.QtWidgets import (
    QWidget, QFormLayout, QSpinBox, QLineEdit, QComboBox, QCheckBox,
)

from .helpers import _as_bool, _BROWSERS


class WebTabMixin:
    def _build_web_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setSpacing(12)
        form.setContentsMargins(28, 20, 28, 20)

        self._w_browser = QComboBox()
        self._w_browser.addItems(_BROWSERS)
        form.addRow("Browser", self._w_browser)

        self._w_headless = QCheckBox("Run browser without a window")
        form.addRow("Headless", self._w_headless)

        self._w_window_width = QSpinBox()
        self._w_window_width.setRange(320, 7680)
        self._w_window_width.setSingleStep(10)
        form.addRow("Window width", self._w_window_width)

        self._w_window_height = QSpinBox()
        self._w_window_height.setRange(320, 4320)
        self._w_window_height.setSingleStep(10)
        form.addRow("Window height", self._w_window_height)

        self._w_randomize_window = QCheckBox("Randomize window size per run")
        form.addRow("Randomize window", self._w_randomize_window)

        self._w_randomize_user_agent = QCheckBox("Randomize user agent per run")
        form.addRow("Randomize user agent", self._w_randomize_user_agent)

        self._w_user_data_dir = QLineEdit()
        self._w_user_data_dir.setPlaceholderText("(blank = temporary profile)")
        form.addRow("User data dir", self._w_user_data_dir)

        self._w_locale = QLineEdit()
        self._w_locale.setPlaceholderText("ko-KR")
        form.addRow("Locale", self._w_locale)

        self._w_implicit_wait = QSpinBox()
        self._w_implicit_wait.setRange(0, 120)
        form.addRow("Implicit wait (sec)", self._w_implicit_wait)

        self._w_page_load_timeout = QSpinBox()
        self._w_page_load_timeout.setRange(0, 600)
        form.addRow("Page load timeout (sec)", self._w_page_load_timeout)

        return w

    def _populate_web(self, web: dict):
        browser = str(web.get("browser", "chrome"))
        idx = self._w_browser.findText(browser)
        self._w_browser.setCurrentIndex(idx if idx >= 0 else 0)
        self._w_headless.setChecked(_as_bool(web.get("headless", "false")))
        self._w_window_width.setValue(int(web.get("window_width", 1280)))
        self._w_window_height.setValue(int(web.get("window_height", 900)))
        self._w_randomize_window.setChecked(_as_bool(web.get("randomize_window", "true")))
        self._w_randomize_user_agent.setChecked(_as_bool(web.get("randomize_user_agent", "true")))
        self._w_user_data_dir.setText(str(web.get("user_data_dir", "") or ""))
        self._w_locale.setText(str(web.get("locale", "ko-KR")))
        self._w_implicit_wait.setValue(int(web.get("implicit_wait", 5)))
        self._w_page_load_timeout.setValue(int(web.get("page_load_timeout", 30)))

    def _collect_web(self) -> dict:
        return {
            "browser":              self._w_browser.currentText(),
            "headless":             "true" if self._w_headless.isChecked() else "false",
            "window_width":         self._w_window_width.value(),
            "window_height":        self._w_window_height.value(),
            "randomize_window":     "true" if self._w_randomize_window.isChecked() else "false",
            "randomize_user_agent": "true" if self._w_randomize_user_agent.isChecked() else "false",
            "user_data_dir":        self._w_user_data_dir.text().strip(),
            "locale":               self._w_locale.text().strip() or "ko-KR",
            "implicit_wait":        self._w_implicit_wait.value(),
            "page_load_timeout":    self._w_page_load_timeout.value(),
        }
