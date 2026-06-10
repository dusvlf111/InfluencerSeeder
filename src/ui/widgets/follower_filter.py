from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QComboBox

_MIN_OPTIONS: list[tuple[str, int]] = [
    ("제한없음", 0),
    ("1천", 1_000),
    ("5천", 5_000),
    ("1만", 10_000),
    ("3만", 30_000),
]
_MAX_OPTIONS: list[tuple[str, int]] = [
    ("제한없음", 0),
    ("5천", 5_000),
    ("1만", 10_000),
    ("3만", 30_000),
    ("5만", 50_000),
    ("10만", 100_000),
]


class FollowerFilterWidget(QWidget):
    """최소/최대 팔로워 필터 콤보박스 쌍."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        layout.addWidget(QLabel("최소"))
        self._min_combo = QComboBox()
        for label, _ in _MIN_OPTIONS:
            self._min_combo.addItem(label)
        layout.addWidget(self._min_combo)

        layout.addWidget(QLabel("최대"))
        self._max_combo = QComboBox()
        for label, _ in _MAX_OPTIONS:
            self._max_combo.addItem(label)
        layout.addWidget(self._max_combo)

    @property
    def min_followers(self) -> int:
        return _MIN_OPTIONS[self._min_combo.currentIndex()][1]

    @property
    def max_followers(self) -> int:
        return _MAX_OPTIONS[self._max_combo.currentIndex()][1]

    def set_values(self, min_val: int, max_val: int):
        for i, (_, v) in enumerate(_MIN_OPTIONS):
            if v == min_val:
                self._min_combo.setCurrentIndex(i)
                break
        for i, (_, v) in enumerate(_MAX_OPTIONS):
            if v == max_val:
                self._max_combo.setCurrentIndex(i)
                break
