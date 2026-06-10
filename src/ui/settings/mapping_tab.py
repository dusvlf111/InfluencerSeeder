"""버튼매핑 탭 Mixin — 자유 편집 단일 테이블.

가이드 이미지/스텝별 카드 구조를 제거하고, selectors.csv 전체를 하나의 자유
편집 테이블로 다룬다. 각 행은 (Step ID 자유입력 | Step Name | Priority | Type |
Selector Value). 임의의 step_id 를 추가해 flow_steps 의 selector_ref 와 연동할 수
있다. 저장 데이터 계약은 기존 save_selectors(list[dict] with priority int) 를 그대로
유지한다 — ``_collect_selectors()`` 가 priority int 를 포함한 list[dict] 를 반환한다.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
)

import core.storage as storage

# 자유 편집 테이블 컬럼.
_MAP_COLS = ["Step ID", "Step Name", "Priority", "Type", "Selector Value"]

# 상단 안내(이미지 없이).
_MAPPING_NOTE = (
    "브라우저에서 요소 우클릭 → 검사(Inspect) → 강조된 요소 우클릭 → "
    "Copy → Copy XPath(또는 Copy selector) → [Selector Value] 칸에 붙여넣기.  "
    "Type 은 xpath / css / coord.  Step ID 는 자유롭게 입력하며 플로우의 "
    "selector_ref 와 연동됩니다.  같은 Step ID 는 Priority 순으로 시도됩니다."
)


class MappingTabMixin:
    def _build_mapping_tab(self) -> QWidget:
        w = QWidget()
        outer = QVBoxLayout(w)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(8)

        note = QLabel(_MAPPING_NOTE)
        note.setObjectName("labelMuted")
        note.setWordWrap(True)
        outer.addWidget(note)

        table = QTableWidget(0, len(_MAP_COLS))
        table.setHorizontalHeaderLabels(_MAP_COLS)
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        table.verticalHeader().setVisible(False)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._mapping_table = table
        outer.addWidget(table)

        # 행 조작 버튼.
        btn_row = QHBoxLayout()
        btn_add = QPushButton("행 추가")
        btn_add.clicked.connect(self._mapping_add_row)
        btn_del = QPushButton("행 삭제")
        btn_del.clicked.connect(self._mapping_del_row)
        btn_up = QPushButton("위로")
        btn_up.clicked.connect(lambda: self._mapping_move_row(-1))
        btn_down = QPushButton("아래로")
        btn_down.clicked.connect(lambda: self._mapping_move_row(1))
        btn_reset = QPushButton("기본값으로 초기화")
        btn_reset.clicked.connect(self._mapping_reset)
        for b in (btn_add, btn_del, btn_up, btn_down, btn_reset):
            btn_row.addWidget(b)
        btn_row.addStretch()
        outer.addLayout(btn_row)

        return w

    def _populate_mapping(self, selectors: list):
        """Fill the free-form table from a (priority-sorted) selector list.

        ``selectors`` follows storage.load_selectors() — already priority-sorted
        with step_id first-appearance order preserved.
        """
        table = self._mapping_table
        table.setRowCount(0)
        for row in selectors:
            sid = row.get("step_id", "")
            if not sid:
                continue
            self._mapping_set_row(
                table, table.rowCount(),
                sid,
                row.get("step_name", ""),
                row.get("priority", ""),
                row.get("selector_type", "xpath"),
                row.get("selector_value", ""),
            )

    @staticmethod
    def _mapping_set_row(table, r, step_id, step_name, priority, sel_type, value):
        if r >= table.rowCount():
            table.insertRow(r)
        table.setItem(r, 0, QTableWidgetItem(str(step_id or "")))
        table.setItem(r, 1, QTableWidgetItem(str(step_name or "")))
        table.setItem(r, 2, QTableWidgetItem(str(priority)))
        table.setItem(r, 3, QTableWidgetItem(str(sel_type or "xpath")))
        table.setItem(r, 4, QTableWidgetItem(str(value or "")))

    def _mapping_add_row(self):
        table = self._mapping_table
        r = table.rowCount()
        self._mapping_set_row(table, r, "", "", 1, "xpath", "")

    def _mapping_del_row(self):
        table = self._mapping_table
        rows = sorted({i.row() for i in table.selectedIndexes()}, reverse=True)
        for r in rows:
            table.removeRow(r)

    def _mapping_move_row(self, delta: int):
        table = self._mapping_table
        rows = sorted({i.row() for i in table.selectedIndexes()})
        if not rows:
            return
        r = rows[0]
        target = r + delta
        if target < 0 or target >= table.rowCount():
            return
        cols = table.columnCount()
        cur = [(table.item(r, c).text() if table.item(r, c) else "") for c in range(cols)]
        oth = [(table.item(target, c).text() if table.item(target, c) else "") for c in range(cols)]
        for c in range(cols):
            table.setItem(r, c, QTableWidgetItem(oth[c]))
            table.setItem(target, c, QTableWidgetItem(cur[c]))
        table.selectRow(target)

    def _mapping_reset(self):
        """Reload the built-in default selector chains into the table."""
        self._populate_mapping(storage.selector_defaults())

    def _collect_selectors(self) -> list[dict]:
        """Flatten the free-form table back to the selectors.csv schema.

        Each non-empty-step_id row becomes one selector dict (priority int,
        step_id, step_name, selector_type, selector_value) — preserving the
        existing save_selectors data contract. Empty step_id rows are dropped.
        """
        table = self._mapping_table
        rows: list[dict] = []
        for r in range(table.rowCount()):
            sid = (table.item(r, 0).text() if table.item(r, 0) else "").strip()
            if not sid:
                continue
            raw_prio = (table.item(r, 2).text() if table.item(r, 2) else "").strip()
            try:
                prio = int(float(raw_prio))
            except (ValueError, TypeError):
                prio = 1
            rows.append({
                "step_id":        sid,
                "step_name":      (table.item(r, 1).text() if table.item(r, 1) else ""),
                "priority":       prio,
                "selector_type":  (table.item(r, 3).text() if table.item(r, 3) else "xpath"),
                "selector_value": (table.item(r, 4).text() if table.item(r, 4) else ""),
            })
        return rows
