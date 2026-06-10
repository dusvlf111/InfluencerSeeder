"""플로우 빌더 탭 (P4) Mixin.

order/phase/step_name/action/selector_ref/param/enabled 스텝 편집 표.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QComboBox, QCheckBox,
)

import core.storage as storage


class FlowBuilderTabMixin:
    _FLOW_COLS = ["order", "phase", "step_name", "action", "selector_ref", "param", "enabled"]
    _FLOW_PHASES = ["pre_loop", "per_tag", "per_post"]

    def _build_flowbuilder_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        note = QLabel(
            "수집 플로우를 스텝 단위로 편집합니다.  action 으로 동작을, selector_ref 로 대상 요소를 지정하고 "
            "enabled 체크를 끄면 그 스텝을 건너뜁니다.  순서는 위/아래 버튼으로 바꿉니다."
        )
        note.setObjectName("labelMuted")
        note.setWordWrap(True)
        layout.addWidget(note)

        self._flow_table = QTableWidget(0, len(self._FLOW_COLS))
        self._flow_table.setHorizontalHeaderLabels(
            ["order", "phase", "step_name", "action", "selector_ref", "param", "enabled"]
        )
        hh = self._flow_table.horizontalHeader()
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        self._flow_table.verticalHeader().setVisible(False)
        # 드롭다운(QComboBox) 셀이 기본 행 높이에 세로로 잘리지 않도록 충분히 키운다.
        self._flow_table.verticalHeader().setDefaultSectionSize(36)
        self._flow_table.setColumnWidth(0, 55)
        self._flow_table.setColumnWidth(1, 90)
        self._flow_table.setColumnWidth(3, 130)
        self._flow_table.setColumnWidth(4, 130)
        self._flow_table.setColumnWidth(6, 70)
        self._flow_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        layout.addWidget(self._flow_table)

        btn_row = QHBoxLayout()
        btn_add = QPushButton("행 추가")
        btn_add.clicked.connect(self._flow_add_row)
        btn_del = QPushButton("행 삭제")
        btn_del.clicked.connect(self._flow_del_row)
        btn_up = QPushButton("위로")
        btn_up.clicked.connect(lambda: self._flow_move_row(-1))
        btn_down = QPushButton("아래로")
        btn_down.clicked.connect(lambda: self._flow_move_row(1))
        btn_reset = QPushButton("기본 플로우로 초기화")
        btn_reset.clicked.connect(self._flow_reset)
        for b in (btn_add, btn_del, btn_up, btn_down):
            btn_row.addWidget(b)
        btn_row.addStretch()
        btn_row.addWidget(btn_reset)
        layout.addLayout(btn_row)
        return w

    def _selector_ref_choices(self) -> list[str]:
        """Distinct selector step_id list (declaration order) for the dropdown."""
        seen: list[str] = []
        for row in (self._selectors or []):
            sid = row.get("step_id", "")
            if sid and sid not in seen:
                seen.append(sid)
        return seen

    def _flow_insert_step_row(self, r: int, data: dict):
        table = self._flow_table
        table.insertRow(r)

        # order (read-only — 위/아래/추가로 재계산)
        order_item = QTableWidgetItem(str(data.get("order", r + 1)))
        order_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
        table.setItem(r, 0, order_item)

        # phase 드롭다운
        phase = QComboBox()
        phase.addItems(self._FLOW_PHASES)
        pv = str(data.get("phase", "per_post"))
        idx = phase.findText(pv)
        if idx < 0:
            phase.addItem(pv)
            idx = phase.findText(pv)
        phase.setCurrentIndex(max(0, idx))
        table.setCellWidget(r, 1, phase)

        # step_name (편집)
        table.setItem(r, 2, QTableWidgetItem(str(data.get("step_name", ""))))

        # action 드롭다운 = FLOW_ACTIONS
        action = QComboBox()
        action.addItems(list(storage.FLOW_ACTIONS))
        av = str(data.get("action", ""))
        ai = action.findText(av)
        if ai < 0 and av:
            action.addItem(av)
            ai = action.findText(av)
        action.setCurrentIndex(max(0, ai))
        table.setCellWidget(r, 3, action)

        # selector_ref 드롭다운 = selectors step_id (+빈값 허용)
        ref = QComboBox()
        ref.setEditable(True)
        ref.addItem("")
        ref.addItems(self._selector_ref_choices())
        rv = str(data.get("selector_ref", ""))
        ri = ref.findText(rv)
        if ri >= 0:
            ref.setCurrentIndex(ri)
        else:
            ref.setEditText(rv)
        table.setCellWidget(r, 4, ref)

        # param (편집)
        table.setItem(r, 5, QTableWidgetItem(str(data.get("param", ""))))

        # enabled 체크박스 (중앙 정렬 래퍼)
        chk = QCheckBox()
        enabled = data.get("enabled", True)
        if isinstance(enabled, bool):
            chk.setChecked(enabled)
        else:
            chk.setChecked(str(enabled).strip().lower() in ("true", "1", "yes", "y", "t"))
        wrap = QWidget()
        wl = QHBoxLayout(wrap)
        wl.setContentsMargins(0, 0, 0, 0)
        wl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        wl.addWidget(chk)
        table.setCellWidget(r, 6, wrap)

    def _flow_renumber(self):
        for r in range(self._flow_table.rowCount()):
            item = self._flow_table.item(r, 0)
            if item is None:
                item = QTableWidgetItem()
                item.setFlags(Qt.ItemFlag.ItemIsEnabled)
                self._flow_table.setItem(r, 0, item)
            item.setText(str(r + 1))

    def _flow_add_row(self):
        r = self._flow_table.rowCount()
        self._flow_insert_step_row(r, {
            "order": r + 1, "phase": "per_post", "step_name": "",
            "action": (storage.FLOW_ACTIONS[0] if storage.FLOW_ACTIONS else ""),
            "selector_ref": "", "param": "", "enabled": True,
        })
        self._flow_renumber()

    def _flow_del_row(self):
        rows = sorted({i.row() for i in self._flow_table.selectedIndexes()}, reverse=True)
        for r in rows:
            self._flow_table.removeRow(r)
        self._flow_renumber()

    def _flow_move_row(self, delta: int):
        rows = sorted({i.row() for i in self._flow_table.selectedIndexes()})
        if not rows:
            return
        r = rows[0]
        target = r + delta
        if target < 0 or target >= self._flow_table.rowCount():
            return
        cur = self._flow_collect_row(r)
        oth = self._flow_collect_row(target)
        self._flow_table.removeRow(r)
        self._flow_table.removeRow(target if target < r else target - 1)
        first, second = sorted((r, target))
        self._flow_insert_step_row(first, oth if first == r else cur)
        self._flow_insert_step_row(second, cur if second == target else oth)
        self._flow_renumber()
        self._flow_table.selectRow(target)

    def _flow_reset(self):
        self._populate_flow_steps(storage.flow_steps_defaults())

    def _flow_collect_row(self, r: int) -> dict:
        table = self._flow_table
        phase = table.cellWidget(r, 1)
        action = table.cellWidget(r, 3)
        ref = table.cellWidget(r, 4)
        wrap = table.cellWidget(r, 6)
        chk = wrap.findChild(QCheckBox) if wrap else None
        return {
            "order":        r + 1,
            "phase":        phase.currentText() if phase else "per_post",
            "step_name":    (table.item(r, 2).text() if table.item(r, 2) else ""),
            "action":       action.currentText() if action else "",
            "selector_ref": (ref.currentText().strip() if ref else ""),
            "param":        (table.item(r, 5).text() if table.item(r, 5) else ""),
            "enabled":      bool(chk.isChecked()) if chk else True,
        }

    def _populate_flow_steps(self, flow_steps: list):
        self._flow_table.setRowCount(0)
        for row_data in flow_steps:
            self._flow_insert_step_row(self._flow_table.rowCount(), row_data)
        self._flow_renumber()

    def _collect_flow_steps(self) -> list[dict]:
        rows: list[dict] = []
        for r in range(self._flow_table.rowCount()):
            rows.append(self._flow_collect_row(r))
        return rows
