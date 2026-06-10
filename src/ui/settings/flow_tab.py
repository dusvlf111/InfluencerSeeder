"""Flow 탭 (§2.4) Mixin — _build_flow_tab / _populate_flow / _collect_flow."""

from PyQt6.QtWidgets import QWidget, QFormLayout, QSpinBox, QCheckBox

from .helpers import _as_bool


class FlowTabMixin:
    def _build_flow_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setSpacing(12)
        form.setContentsMargins(28, 20, 28, 20)

        self._fl_max_tags = QSpinBox()
        self._fl_max_tags.setRange(1, 50)
        self._fl_max_tags.setToolTip(
            "How many tag suggestions to cycle through.\n"
            "Search is re-run for each subsequent suggestion."
        )
        form.addRow("Max tag suggestions", self._fl_max_tags)

        self._fl_tag_start_index = QSpinBox()
        self._fl_tag_start_index.setRange(0, 49)
        form.addRow("Tag start index", self._fl_tag_start_index)

        self._fl_posts_per_tag = QSpinBox()
        self._fl_posts_per_tag.setRange(1, 200)
        self._fl_posts_per_tag.setToolTip("Posts to collect per tag suggestion")
        form.addRow("Posts per tag", self._fl_posts_per_tag)

        self._fl_scroll_max_attempts = QSpinBox()
        self._fl_scroll_max_attempts.setRange(0, 200)
        form.addRow("Scroll max attempts", self._fl_scroll_max_attempts)

        self._fl_skip_visited_profile = QCheckBox("Skip profiles already collected")
        form.addRow("Skip visited profile", self._fl_skip_visited_profile)

        self._fl_stop_on_consecutive_miss = QSpinBox()
        self._fl_stop_on_consecutive_miss.setRange(0, 1000)
        self._fl_stop_on_consecutive_miss.setToolTip(
            "Stop a tag after this many consecutive duplicate/filtered posts (0 = never)."
        )
        form.addRow("Stop on consecutive miss", self._fl_stop_on_consecutive_miss)

        return w

    def _populate_flow(self, flow: dict):
        self._fl_max_tags.setValue(int(flow.get("max_tags", 3)))
        self._fl_tag_start_index.setValue(int(flow.get("tag_start_index", 0)))
        self._fl_posts_per_tag.setValue(int(flow.get("posts_per_tag", 5)))
        self._fl_scroll_max_attempts.setValue(int(flow.get("scroll_max_attempts", 15)))
        self._fl_skip_visited_profile.setChecked(_as_bool(flow.get("skip_visited_profile", "true")))
        self._fl_stop_on_consecutive_miss.setValue(int(flow.get("stop_on_consecutive_miss", 10)))

    def _collect_flow(self) -> dict:
        return {
            "max_tags":                 self._fl_max_tags.value(),
            "tag_start_index":          self._fl_tag_start_index.value(),
            "posts_per_tag":            self._fl_posts_per_tag.value(),
            "scroll_max_attempts":      self._fl_scroll_max_attempts.value(),
            "skip_visited_profile":     "true" if self._fl_skip_visited_profile.isChecked() else "false",
            "stop_on_consecutive_miss": self._fl_stop_on_consecutive_miss.value(),
        }
