"""수집 설정 탭 Mixin — posts_per_tag / skip_first_post."""

from PyQt6.QtWidgets import QWidget, QFormLayout, QSpinBox, QCheckBox

from .helpers import _as_bool


class FlowTabMixin:
    def _build_flow_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setSpacing(12)
        form.setContentsMargins(28, 20, 28, 20)

        self._fl_posts_per_tag = QSpinBox()
        self._fl_posts_per_tag.setRange(1, 200)
        self._fl_posts_per_tag.setToolTip(
            "키워드 1개당 확인할 게시물 수. 이 수만큼 게시물을 열어보고 다음 키워드로 넘어감."
        )
        form.addRow("키워드당 게시물 수", self._fl_posts_per_tag)

        self._fl_skip_first = QCheckBox("해시태그 첫 번째 게시물 건너뛰기")
        self._fl_skip_first.setToolTip(
            "해시태그 탐색 페이지의 첫 번째(상단 고정) 게시물은 광고일 수 있으므로 건너뜁니다."
        )
        form.addRow("첫 게시물 건너뛰기", self._fl_skip_first)

        return w

    def _populate_flow(self, flow: dict):
        self._fl_posts_per_tag.setValue(int(flow.get("posts_per_tag", 5)))
        self._fl_skip_first.setChecked(_as_bool(flow.get("skip_first_post", "true")))

    def _collect_flow(self) -> dict:
        return {
            "posts_per_tag":   self._fl_posts_per_tag.value(),
            "skip_first_post": "true" if self._fl_skip_first.isChecked() else "false",
        }
