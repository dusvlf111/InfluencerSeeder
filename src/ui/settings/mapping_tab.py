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
    QComboBox, QScrollArea,
)

import core.storage as storage

# 자유 편집 테이블 컬럼.
_MAP_COLS = ["Step ID", "Step Name", "Priority", "Type", "Selector Value"]

# Type 셀 드롭다운 항목.
_MAP_TYPES = ["xpath", "css", "coord"]

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
        # 고정폭으로 보기 좋게(콤보/편집이 잘리지 않도록). Value 만 Stretch 유지.
        # Step ID: Interactive, Step Name: Stretch(긴 한국어 이름 수용), Priority/Type: Interactive
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Interactive)
        table.setColumnWidth(0, 130)   # Step ID
        table.setColumnWidth(2, 55)    # Priority (숫자)
        table.setColumnWidth(3, 80)    # Type (xpath/css/coord)
        table.setColumnWidth(4, 220)   # Selector Value (기본폭, 드래그로 확장 가능)
        header.setMinimumSectionSize(55)
        table.setMinimumWidth(600)
        table.verticalHeader().setVisible(False)
        # 콤보/편집 셀이 세로로 잘리지 않도록 행 높이를 키운다.
        table.verticalHeader().setDefaultSectionSize(36)
        # 세로로 더 길게 — 좁은(390px) 창에서도 한 번에 많은 행이 보이도록.
        # 컨텐츠가 넘치면 아래 QScrollArea 가 스크롤을 제공한다.
        table.setMinimumHeight(560)
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

        # 고정 390x844 창에서 테이블/버튼이 잘리지 않도록 전체를 스크롤 영역에 둔다.
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(w)
        return scroll

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
    def _mapping_make_type_combo(sel_type):
        """Type 셀용 드롭다운(xpath/css/coord). 미지 값이면 항목 추가 후 선택."""
        combo = QComboBox()
        combo.setEditable(False)
        combo.addItems(_MAP_TYPES)
        tv = str(sel_type or "xpath")
        idx = combo.findText(tv)
        if idx < 0:
            combo.addItem(tv)
            idx = combo.findText(tv)
        combo.setCurrentIndex(max(0, idx))
        return combo

    @classmethod
    def _mapping_set_type(cls, table, r, sel_type):
        table.setCellWidget(r, 3, cls._mapping_make_type_combo(sel_type))

    @classmethod
    def _mapping_set_row(cls, table, r, step_id, step_name, priority, sel_type, value):
        if r >= table.rowCount():
            table.insertRow(r)
        table.setItem(r, 0, QTableWidgetItem(str(step_id or "")))
        table.setItem(r, 1, QTableWidgetItem(str(step_name or "")))
        table.setItem(r, 2, QTableWidgetItem(str(priority)))
        cls._mapping_set_type(table, r, sel_type)
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

        def _cell_text(row, c):
            if c == 3:  # Type 은 콤보 위젯
                w = table.cellWidget(row, c)
                return w.currentText() if w else "xpath"
            it = table.item(row, c)
            return it.text() if it else ""

        cur = [_cell_text(r, c) for c in range(cols)]
        oth = [_cell_text(target, c) for c in range(cols)]
        for c in range(cols):
            if c == 3:  # Type 셀: 콤보 위젯을 재설정해 값 보존
                self._mapping_set_type(table, r, oth[c])
                self._mapping_set_type(table, target, cur[c])
            else:
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
            type_combo = table.cellWidget(r, 3)
            sel_type = type_combo.currentText() if type_combo else "xpath"
            rows.append({
                "step_id":        sid,
                "step_name":      (table.item(r, 1).text() if table.item(r, 1) else ""),
                "priority":       prio,
                "selector_type":  (sel_type or "xpath"),
                "selector_value": (table.item(r, 4).text() if table.item(r, 4) else ""),
            })
        return rows
