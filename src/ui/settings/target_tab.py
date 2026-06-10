"""Target 탭 (§2.5) Mixin — _build_target_tab / _populate_target / _collect_target."""

from PyQt6.QtWidgets import QWidget, QFormLayout, QSpinBox, QLineEdit, QComboBox

from .helpers import _MODES


class TargetTabMixin:
    def _build_target_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setSpacing(12)
        form.setContentsMargins(28, 20, 28, 20)

        self._t_min_followers = QSpinBox()
        self._t_min_followers.setRange(0, 100_000_000)
        self._t_min_followers.setSingleStep(1000)
        form.addRow("Min followers (0 = no limit)", self._t_min_followers)

        self._t_max_followers = QSpinBox()
        self._t_max_followers.setRange(0, 100_000_000)
        self._t_max_followers.setSingleStep(1000)
        form.addRow("Max followers (0 = no limit)", self._t_max_followers)

        self._t_min_following = QSpinBox()
        self._t_min_following.setRange(0, 100_000_000)
        self._t_min_following.setSingleStep(100)
        form.addRow("Min following (0 = no limit)", self._t_min_following)

        self._t_max_following = QSpinBox()
        self._t_max_following.setRange(0, 100_000_000)
        self._t_max_following.setSingleStep(100)
        form.addRow("Max following (0 = no limit)", self._t_max_following)

        self._t_min_posts = QSpinBox()
        self._t_min_posts.setRange(0, 1_000_000)
        form.addRow("Min posts (0 = no limit)", self._t_min_posts)

        self._t_keyword = QLineEdit()
        self._t_keyword.setPlaceholderText("hashtag or keyword to search")
        form.addRow("Keyword", self._t_keyword)

        self._t_mode = QComboBox()
        self._t_mode.addItems(_MODES)
        form.addRow("Mode", self._t_mode)

        return w

    def _populate_target(self, target: dict):
        self._t_min_followers.setValue(int(target.get("min_followers", 0)))
        self._t_max_followers.setValue(int(target.get("max_followers", 0)))
        self._t_min_following.setValue(int(target.get("min_following", 0)))
        self._t_max_following.setValue(int(target.get("max_following", 0)))
        self._t_min_posts.setValue(int(target.get("min_posts", 0)))
        self._t_keyword.setText(str(target.get("keyword", "") or ""))
        mode = str(target.get("mode", "hashtag"))
        idx = self._t_mode.findText(mode)
        self._t_mode.setCurrentIndex(idx if idx >= 0 else 0)

    def _collect_target(self) -> dict:
        return {
            "min_followers": self._t_min_followers.value(),
            "max_followers": self._t_max_followers.value(),
            "min_following": self._t_min_following.value(),
            "max_following": self._t_max_following.value(),
            "min_posts":     self._t_min_posts.value(),
            "keyword":       self._t_keyword.text().strip(),
            "mode":          self._t_mode.currentText(),
        }
