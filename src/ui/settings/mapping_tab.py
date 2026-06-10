"""버튼매핑 탭 (P3) Mixin.

selectors.csv 의 step_id 별로 카드(QScrollArea)를 만든다: 상단에 가이드 스크린샷,
그 아래 "XPath 복사하는 법" 설명, 그 아래 해당 step 의 셀렉터 후보 표
(priority/type/value 행 추가·삭제·정렬). 저장 데이터 계약은 기존
save_selectors(list[dict] with priority int) 를 그대로 유지한다.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView, QScrollArea,
)

from core.assets import guide_image_for_selector

# Guide text shown on every button-mapping card.
_MAPPING_GUIDE = (
    "브라우저에서 요소 우클릭 → 검사(Inspect) → 강조된 요소 우클릭 → "
    "Copy → Copy XPath(또는 Copy selector) → 아래 값 칸에 붙여넣기.  "
    "type 은 xpath / css / coord."
)

# Selector-table columns for each mapping card.
_SEL_COLS = ["priority", "type", "value"]


class MappingTabMixin:
    def _build_mapping_tab(self) -> QWidget:
        w = QWidget()
        outer = QVBoxLayout(w)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._mapping_host = QWidget()
        self._mapping_layout = QVBoxLayout(self._mapping_host)
        self._mapping_layout.setContentsMargins(12, 12, 12, 12)
        self._mapping_layout.setSpacing(16)

        note = QLabel(
            "각 스텝의 버튼/요소를 찾는 셀렉터 후보입니다.  "
            "인스타그램 DOM 변경으로 수집이 깨지면 여기서 우선순위(priority) 순으로 후보를 편집하세요."
        )
        note.setObjectName("labelMuted")
        note.setWordWrap(True)
        self._mapping_layout.addWidget(note)

        # 카드 컨테이너는 _populate_mapping() 이 동적으로 채운다.
        self._mapping_cards_container = QVBoxLayout()
        self._mapping_cards_container.setSpacing(16)
        self._mapping_layout.addLayout(self._mapping_cards_container)
        self._mapping_layout.addStretch()

        scroll.setWidget(self._mapping_host)
        outer.addWidget(scroll)
        return w

    def _build_mapping_card(self, step_id: str, step_name: str) -> QFrame:
        card = QFrame()
        card.setObjectName("mappingCard")
        cl = QVBoxLayout(card)
        cl.setContentsMargins(16, 16, 16, 16)
        cl.setSpacing(8)

        title = QLabel(f"{step_id}  —  {step_name}" if step_name else step_id)
        title.setObjectName("cardTitle")
        cl.addWidget(title)

        # 가이드 스크린샷 (있을 때만)
        img_path = guide_image_for_selector(step_id)
        if img_path is not None and img_path.exists():
            pix = QPixmap(str(img_path))
            if not pix.isNull():
                img = QLabel()
                img.setObjectName("guideImage")
                img.setPixmap(
                    pix.scaled(
                        220, 150,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
                img.setAlignment(Qt.AlignmentFlag.AlignLeft)
                cl.addWidget(img)

        guide = QLabel(_MAPPING_GUIDE)
        guide.setObjectName("mappingGuide")
        guide.setWordWrap(True)
        cl.addWidget(guide)

        # 셀렉터 후보 표 (priority / type / value)
        table = QTableWidget(0, len(_SEL_COLS))
        table.setHorizontalHeaderLabels(["priority", "type", "value"])
        table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch
        )
        table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        table.verticalHeader().setVisible(False)
        table.setColumnWidth(0, 70)
        table.setColumnWidth(1, 90)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setMinimumHeight(120)
        cl.addWidget(table)

        # 행 조작 버튼
        btn_row = QHBoxLayout()
        btn_add = QPushButton("후보 추가")
        btn_add.clicked.connect(lambda _=False, t=table: self._mapping_add_row(t))
        btn_del = QPushButton("선택 삭제")
        btn_del.clicked.connect(lambda _=False, t=table: self._mapping_del_row(t))
        btn_up = QPushButton("위로")
        btn_up.clicked.connect(lambda _=False, t=table: self._mapping_move_row(t, -1))
        btn_down = QPushButton("아래로")
        btn_down.clicked.connect(lambda _=False, t=table: self._mapping_move_row(t, 1))
        for b in (btn_add, btn_del, btn_up, btn_down):
            btn_row.addWidget(b)
        btn_row.addStretch()
        cl.addLayout(btn_row)

        self._mapping_tables[step_id] = table
        return card

    def _populate_mapping(self, selectors: list):
        """(Re)build one card per distinct step_id and fill its candidate table.

        ``selectors`` is already priority-sorted with step_id first-appearance
        order preserved (storage.load_selectors). step_name comes from the first
        row of each group.
        """
        # 기존 카드 제거
        self._mapping_tables.clear()
        while self._mapping_cards_container.count():
            item = self._mapping_cards_container.takeAt(0)
            child = item.widget()
            if child is not None:
                child.setParent(None)
                child.deleteLater()

        # step_id → 후보 행 그룹 (등장 순서 유지)
        groups: dict[str, list[dict]] = {}
        names: dict[str, str] = {}
        for row in selectors:
            sid = row.get("step_id", "")
            if not sid:
                continue
            groups.setdefault(sid, []).append(row)
            if sid not in names:
                names[sid] = row.get("step_name", "")
        # step_id → step_name 보존 (collect 시 selectors.csv 계약 유지용)
        self._mapping_names = dict(names)

        for sid, rows in groups.items():
            card = self._build_mapping_card(sid, names.get(sid, ""))
            self._mapping_cards_container.addWidget(card)
            table = self._mapping_tables[sid]
            for row_data in rows:
                self._mapping_set_row(
                    table,
                    table.rowCount(),
                    row_data.get("priority", ""),
                    row_data.get("selector_type", "xpath"),
                    row_data.get("selector_value", ""),
                )

    @staticmethod
    def _mapping_set_row(table, r, priority, sel_type, value):
        if r >= table.rowCount():
            table.insertRow(r)
        table.setItem(r, 0, QTableWidgetItem(str(priority)))
        table.setItem(r, 1, QTableWidgetItem(str(sel_type or "xpath")))
        table.setItem(r, 2, QTableWidgetItem(str(value or "")))

    def _mapping_add_row(self, table):
        r = table.rowCount()
        # 새 후보의 기본 priority = 현재 행 수 + 1
        self._mapping_set_row(table, r, r + 1, "xpath", "")

    def _mapping_del_row(self, table):
        rows = sorted({i.row() for i in table.selectedIndexes()}, reverse=True)
        for r in rows:
            table.removeRow(r)

    def _mapping_move_row(self, table, delta: int):
        rows = sorted({i.row() for i in table.selectedIndexes()})
        if not rows:
            return
        r = rows[0]
        target = r + delta
        if target < 0 or target >= table.rowCount():
            return
        cur = [(table.item(r, c).text() if table.item(r, c) else "") for c in range(table.columnCount())]
        oth = [(table.item(target, c).text() if table.item(target, c) else "") for c in range(table.columnCount())]
        for c in range(table.columnCount()):
            table.setItem(r, c, QTableWidgetItem(oth[c]))
            table.setItem(target, c, QTableWidgetItem(cur[c]))
        table.selectRow(target)

    def _collect_selectors(self) -> list[dict]:
        """Flatten the button-mapping cards back to the selectors.csv schema.

        Each card's table rows become one selector dict (priority int, step_id,
        step_name, selector_type, selector_value) — preserving the existing
        save_selectors data contract.
        """
        rows: list[dict] = []
        for sid, table in self._mapping_tables.items():
            step_name = self._mapping_names.get(sid, "")
            for r in range(table.rowCount()):
                raw_prio = (table.item(r, 0).text() if table.item(r, 0) else "").strip()
                try:
                    prio = int(float(raw_prio))
                except (ValueError, TypeError):
                    prio = r + 1
                rows.append({
                    "step_id":        sid,
                    "step_name":      step_name,
                    "priority":       prio,
                    "selector_type":  (table.item(r, 1).text() if table.item(r, 1) else "xpath"),
                    "selector_value": (table.item(r, 2).text() if table.item(r, 2) else ""),
                })
        return rows
