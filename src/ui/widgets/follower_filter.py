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


def _nearest_index(options: list[tuple[str, int]], value: int) -> int:
    """value 와 가장 가까운 프리셋의 인덱스. 0 은 '제한없음'(정확히 0일 때만)."""
    value = int(value or 0)
    if value <= 0:
        return 0
    best_i, best_d = 0, None
    for i, (_, v) in enumerate(options):
        d = abs(v - value)
        if best_d is None or d < best_d:
            best_i, best_d = i, d
    return best_i


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
        # 콤보는 프리셋 값만 가지므로(타겟 탭은 임의값) 정확히 일치하는 항목이
        # 없으면 가장 가까운 프리셋으로 스냅 — 동기화 시 0(제한없음)으로 리셋 방지.
        self._min_combo.setCurrentIndex(_nearest_index(_MIN_OPTIONS, min_val))
        self._max_combo.setCurrentIndex(_nearest_index(_MAX_OPTIONS, max_val))
