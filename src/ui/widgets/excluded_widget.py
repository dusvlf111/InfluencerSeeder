from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QPushButton, QListWidget, QGroupBox,
)
from PyQt6.QtCore import pyqtSignal

import core.storage as storage


class ExcludedAccountsWidget(QGroupBox):
    """제외 계정 관리 위젯 (추가/삭제, JSON 영구 저장)."""

    changed = pyqtSignal(list)   # 변경 시 현재 목록 emit

    def __init__(self, parent=None):
        super().__init__("제외 계정", parent)
        self._accounts: list[str] = storage.load_excluded()
        self._build_ui()
        self._refresh()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        add_row = QHBoxLayout()
        self._input = QLineEdit()
        self._input.setPlaceholderText("계정명 입력 (@생략, 쉼표 구분)")
        self._input.returnPressed.connect(self._add)
        btn_add = QPushButton("추가")
        btn_add.setFixedWidth(52)
        btn_add.clicked.connect(self._add)
        add_row.addWidget(self._input)
        add_row.addWidget(btn_add)
        layout.addLayout(add_row)

        self._list = QListWidget()
        self._list.setMaximumHeight(120)
        layout.addWidget(self._list)

        btn_del = QPushButton("선택 삭제")
        btn_del.clicked.connect(self._remove)
        layout.addWidget(btn_del)

    def _refresh(self):
        self._list.clear()
        for acc in sorted(self._accounts):
            self._list.addItem("@" + acc)

    def _save(self):
        storage.save_excluded(self._accounts)
        self._refresh()
        self.changed.emit(list(self._accounts))

    def _add(self):
        raw = self._input.text().strip()
        if not raw:
            return
        for part in raw.replace(",", " ").split():
            acc = part.lstrip("@").lower()
            if acc and acc not in self._accounts:
                self._accounts.append(acc)
        self._input.clear()
        self._save()

    def _remove(self):
        for item in self._list.selectedItems():
            acc = item.text().lstrip("@").lower()
            if acc in self._accounts:
                self._accounts.remove(acc)
        self._save()

    def reload(self, accounts: list[str]):
        """외부(구글 시트 등)에서 계정 목록을 병합."""
        merged = sorted(set(self._accounts) | set(accounts))
        self._accounts = merged
        self._save()

    @property
    def accounts(self) -> list[str]:
        return list(self._accounts)
