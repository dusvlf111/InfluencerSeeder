"""Delays 탭 (시간텀, §2.3) Mixin — _build_delays_tab / _populate_delays / _collect_delays."""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem, QHeaderView,
)

import core.storage as storage

# step_id → human label (시간텀 탭). load_delays() 의 {step_id:(min,max)} 키와 일치.
_DELAY_STEPS = [
    ("step1",       "Step 1 — Click Search Icon"),
    ("step2",       "Step 2 — Type Hashtag"),
    ("step3",       "Step 3 — Select Tag Suggestion"),
    ("step4",       "Step 4 — Open Post"),
    ("step5",       "Step 5 — Navigate to Profile"),
    ("step6",       "Step 6 — Save Profile Data"),
    ("back",        "Return to Tag Grid"),
    ("scroll",      "Scroll (per scroll)"),
    ("typing_char", "Typing (per character)"),
    ("screenshot",  "Profile Screenshot (before capture)"),
]


class DelaysTabMixin:
    def _build_delays_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        note = QLabel(
            "Random delay applied after each step.  "
            "Longer delays reduce detection risk."
        )
        note.setObjectName("labelMuted")
        note.setWordWrap(True)
        layout.addWidget(note)

        self._delay_table = QTableWidget(len(_DELAY_STEPS), 3)
        self._delay_table.setHorizontalHeaderLabels(["Step", "Min (sec)", "Max (sec)"])
        self._delay_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self._delay_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents
        )
        self._delay_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents
        )
        self._delay_table.setFont(QFont("", 11))
        self._delay_table.verticalHeader().setVisible(False)
        # 입력 칸이 잘리지 않도록 행 높이를 넉넉히.
        self._delay_table.verticalHeader().setDefaultSectionSize(40)
        self._delay_table.setColumnWidth(1, 110)
        self._delay_table.setColumnWidth(2, 110)

        for row, (key, label) in enumerate(_DELAY_STEPS):
            name_item = QTableWidgetItem(label)
            name_item.setFlags(Qt.ItemFlag.ItemIsEnabled)  # read-only
            self._delay_table.setItem(row, 0, name_item)
            self._delay_table.setItem(row, 1, QTableWidgetItem(""))
            self._delay_table.setItem(row, 2, QTableWidgetItem(""))

        layout.addWidget(self._delay_table)
        return w

    def _populate_delays(self, delays: dict):
        for row, (key, _) in enumerate(_DELAY_STEPS):
            lo, hi = delays.get(key, (1.0, 2.0))
            self._delay_table.item(row, 1).setText(str(lo))
            self._delay_table.item(row, 2).setText(str(hi))

    def _collect_delays(self) -> dict:
        """Return {step_id: (min, max)}; bad cells fall back to defaults."""
        defaults = storage.delay_defaults()
        result: dict = {}
        for row, (key, _) in enumerate(_DELAY_STEPS):
            base = defaults.get(key, (0.0, 0.0))
            try:
                lo = float(self._delay_table.item(row, 1).text())
            except (ValueError, AttributeError):
                lo = base[0]
            try:
                hi = float(self._delay_table.item(row, 2).text())
            except (ValueError, AttributeError):
                hi = base[1]
            result[key] = (lo, hi)
        return result
