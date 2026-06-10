"""Excluded 탭 Mixin — 수집 제외 계정 목록 편집."""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QTableWidget, QTableWidgetItem, QHeaderView,
)


class ExcludedTabMixin:
    def _build_excluded_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        note = QLabel("Accounts in this list are never collected.")
        note.setObjectName("labelMuted")
        layout.addWidget(note)

        add_row = QHBoxLayout()
        self._excl_input = QLineEdit()
        self._excl_input.setPlaceholderText("username  (comma-separated for multiple)")
        self._excl_input.returnPressed.connect(self._add_excluded)
        btn_add = QPushButton("Add")
        btn_add.setFixedWidth(60)
        btn_add.clicked.connect(self._add_excluded)
        add_row.addWidget(self._excl_input)
        add_row.addWidget(btn_add)
        layout.addLayout(add_row)

        self._excl_table = QTableWidget(0, 1)
        self._excl_table.setHorizontalHeaderLabels(["Username"])
        self._excl_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self._excl_table.verticalHeader().setVisible(False)
        layout.addWidget(self._excl_table)

        btn_del = QPushButton("Remove selected")
        btn_del.clicked.connect(self._remove_excluded)
        layout.addWidget(btn_del)
        return w

    def _populate_excluded(self, excluded: list):
        self._excl_table.setRowCount(0)
        for username in excluded:
            r = self._excl_table.rowCount()
            self._excl_table.insertRow(r)
            self._excl_table.setItem(r, 0, QTableWidgetItem(username))

    def _collect_excluded(self) -> list[str]:
        accounts = []
        for r in range(self._excl_table.rowCount()):
            item = self._excl_table.item(r, 0)
            if item:
                u = item.text().strip().lstrip("@")
                if u:
                    accounts.append(u)
        return accounts

    def _add_excluded(self):
        raw = self._excl_input.text().strip()
        if not raw:
            return
        existing = self._collect_excluded()
        existing_set = {u.lower() for u in existing}
        for part in raw.replace(",", " ").split():
            u = part.lstrip("@").lower()
            if u and u not in existing_set:
                existing.append(u)
                existing_set.add(u)
        self._excl_input.clear()
        # Refresh table
        self._excl_table.setRowCount(0)
        for username in sorted(existing):
            r = self._excl_table.rowCount()
            self._excl_table.insertRow(r)
            self._excl_table.setItem(r, 0, QTableWidgetItem(username))

    def _remove_excluded(self):
        rows_to_del = sorted(
            {idx.row() for idx in self._excl_table.selectedIndexes()},
            reverse=True,
        )
        for r in rows_to_del:
            self._excl_table.removeRow(r)
