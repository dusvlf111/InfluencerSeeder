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
            "쉼표로 키워드를 여러 개 입력하면 각 키워드가 하나의 태그로 검색됩니다.\n"
            "이 값은 키워드 검색 방식에선 사용되지 않습니다(하위호환 유지)."
        )
        form.addRow("최대 태그 수(레거시)", self._fl_max_tags)

        self._fl_tag_start_index = QSpinBox()
        self._fl_tag_start_index.setRange(0, 49)
        form.addRow("시작 태그 인덱스", self._fl_tag_start_index)

        self._fl_posts_per_tag = QSpinBox()
        self._fl_posts_per_tag.setRange(1, 200)
        self._fl_posts_per_tag.setToolTip(
            "키워드 1개당 수집할 게시물 수. 이만큼 모으면 다음 키워드로 넘어감"
        )
        form.addRow("태그(키워드)당 게시물 수", self._fl_posts_per_tag)

        self._fl_scroll_max_attempts = QSpinBox()
        self._fl_scroll_max_attempts.setRange(0, 200)
        form.addRow("그리드 최대 스크롤", self._fl_scroll_max_attempts)

        self._fl_skip_visited_profile = QCheckBox("이미 수집한 프로필 건너뛰기")
        form.addRow("방문한 프로필 건너뛰기", self._fl_skip_visited_profile)

        self._fl_stop_on_consecutive_miss = QSpinBox()
        self._fl_stop_on_consecutive_miss.setRange(0, 1000)
        self._fl_stop_on_consecutive_miss.setToolTip(
            "연속으로 중복/필터 제외된 게시물이 이 수만큼 나오면 해당 태그를 중단(0 = 사용 안 함)."
        )
        form.addRow("연속 미수집 시 중단", self._fl_stop_on_consecutive_miss)

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
