import sys
from pathlib import Path

from PyQt6.QtCore import QProcess, pyqtSignal, Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QGroupBox, QFormLayout, QSpinBox,
    QDoubleSpinBox, QTextEdit, QFrame, QMessageBox,
    QTabWidget, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QLineEdit,
)

import core.storage as storage

_DELAY_STEPS = [
    ("step1", "Step 1 — Click Search Icon"),
    ("step2", "Step 2 — Type Hashtag"),
    ("step3", "Step 3 — Select Tag Suggestion"),
    ("step4", "Step 4 — Open Post"),
    ("step5", "Step 5 — Navigate to Profile"),
    ("step6", "Step 6 — Save Profile Data"),
    ("back",  "Return to Tag Grid"),
]


class SettingsView(QWidget):
    back_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._settings: dict = {}
        self._process: QProcess | None = None
        self._build_ui()

    # ── Public API ────────────────────────────────────────────────────────────

    def load(self):
        """Read all CSV files and populate UI fields."""
        self._settings  = storage.load_settings()
        self._selectors = storage.load_selectors()
        self._excluded  = storage.load_excluded()
        self._populate()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(0)
        root.setContentsMargins(0, 0, 0, 0)

        # Header bar
        header = QFrame()
        header.setObjectName("settingsHeader")
        hl = QHBoxLayout(header)
        hl.setContentsMargins(16, 10, 16, 10)

        btn_back = QPushButton("<< Back")
        btn_back.clicked.connect(self.back_requested)
        hl.addWidget(btn_back)

        title = QLabel("Settings")
        title.setObjectName("labelAccent")
        hl.addStretch()
        hl.addWidget(title)
        hl.addStretch()

        btn_save = QPushButton("Save All")
        btn_save.setObjectName("btnPrimary")
        btn_save.clicked.connect(self._save_all)
        hl.addWidget(btn_save)

        root.addWidget(header)

        # Tab widget
        self._tabs = QTabWidget()
        self._tabs.addTab(self._build_collection_tab(), "Collection")
        self._tabs.addTab(self._build_delays_tab(),     "Delays")
        self._tabs.addTab(self._build_selectors_tab(),  "Selectors")
        self._tabs.addTab(self._build_excluded_tab(),   "Excluded")
        self._tabs.addTab(self._build_deps_tab(),       "Dependencies")
        root.addWidget(self._tabs)

    # ── Tab: Collection ───────────────────────────────────────────────────────

    def _build_collection_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setSpacing(12)
        form.setContentsMargins(28, 20, 28, 20)

        self._f_min_followers = QSpinBox()
        self._f_min_followers.setRange(0, 10_000_000)
        self._f_min_followers.setSingleStep(1000)
        form.addRow("Min followers (0 = no limit)", self._f_min_followers)

        self._f_max_followers = QSpinBox()
        self._f_max_followers.setRange(0, 10_000_000)
        self._f_max_followers.setSingleStep(1000)
        form.addRow("Max followers (0 = no limit)", self._f_max_followers)

        self._f_posts_per_tag = QSpinBox()
        self._f_posts_per_tag.setRange(1, 100)
        self._f_posts_per_tag.setToolTip("Posts to collect per tag suggestion")
        form.addRow("Posts per tag", self._f_posts_per_tag)

        self._f_max_tags = QSpinBox()
        self._f_max_tags.setRange(1, 20)
        self._f_max_tags.setToolTip(
            "How many tag suggestions to cycle through.\n"
            "Search is re-run for each subsequent suggestion."
        )
        form.addRow("Max tag suggestions", self._f_max_tags)

        return w

    # ── Tab: Delays ───────────────────────────────────────────────────────────

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
        self._delay_table.verticalHeader().setVisible(False)
        self._delay_table.setColumnWidth(1, 90)
        self._delay_table.setColumnWidth(2, 90)

        for row, (key, label) in enumerate(_DELAY_STEPS):
            name_item = QTableWidgetItem(label)
            name_item.setFlags(Qt.ItemFlag.ItemIsEnabled)  # read-only
            self._delay_table.setItem(row, 0, name_item)
            self._delay_table.setItem(row, 1, QTableWidgetItem(""))
            self._delay_table.setItem(row, 2, QTableWidgetItem(""))

        layout.addWidget(self._delay_table)
        return w

    # ── Tab: Selectors ────────────────────────────────────────────────────────

    def _build_selectors_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        note = QLabel(
            "HTML selectors for each scraping step.  "
            "Edit when Instagram updates its DOM and scraping breaks."
        )
        note.setObjectName("labelMuted")
        note.setWordWrap(True)
        layout.addWidget(note)

        self._sel_table = QTableWidget(0, 4)
        self._sel_table.setHorizontalHeaderLabels(
            ["Step ID", "Step Name", "Type (xpath/css)", "Selector Value"]
        )
        self._sel_table.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeMode.Stretch
        )
        self._sel_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents
        )
        self._sel_table.verticalHeader().setVisible(False)
        self._sel_table.setColumnWidth(0, 120)
        self._sel_table.setColumnWidth(2, 100)
        layout.addWidget(self._sel_table)

        btn_reset = QPushButton("Reset selectors to defaults")
        btn_reset.clicked.connect(self._reset_selectors)
        layout.addWidget(btn_reset)
        return w

    # ── Tab: Excluded ─────────────────────────────────────────────────────────

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

    # ── Tab: Dependencies ─────────────────────────────────────────────────────

    def _build_deps_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(8)

        btn = QPushButton("pip install requirements.txt")
        btn.clicked.connect(self._run_pip)
        layout.addWidget(btn)

        self._pip_log = QTextEdit()
        self._pip_log.setReadOnly(True)
        self._pip_log.setMinimumHeight(120)
        layout.addWidget(self._pip_log)
        layout.addStretch()
        return w

    # ── Populate / collect ────────────────────────────────────────────────────

    def _populate(self):
        s = self._settings

        # Collection tab
        self._f_min_followers.setValue(int(s.get("min_followers", 0)))
        self._f_max_followers.setValue(int(s.get("max_followers", 0)))
        self._f_posts_per_tag.setValue(int(s.get("posts_per_tag", 5)))
        self._f_max_tags.setValue(int(s.get("max_tags", 3)))

        # Delays tab
        for row, (key, _) in enumerate(_DELAY_STEPS):
            min_val = str(s.get(f"{key}_delay_min", "1.0"))
            max_val = str(s.get(f"{key}_delay_max", "2.0"))
            self._delay_table.item(row, 1).setText(min_val)
            self._delay_table.item(row, 2).setText(max_val)

        # Selectors tab
        self._sel_table.setRowCount(0)
        for row_data in self._selectors:
            r = self._sel_table.rowCount()
            self._sel_table.insertRow(r)
            step_id_item = QTableWidgetItem(row_data.get("step_id", ""))
            step_id_item.setFlags(Qt.ItemFlag.ItemIsEnabled)  # read-only
            self._sel_table.setItem(r, 0, step_id_item)
            self._sel_table.setItem(r, 1, QTableWidgetItem(row_data.get("step_name", "")))
            self._sel_table.setItem(r, 2, QTableWidgetItem(row_data.get("selector_type", "xpath")))
            self._sel_table.setItem(r, 3, QTableWidgetItem(row_data.get("selector_value", "")))

        # Excluded tab
        self._excl_table.setRowCount(0)
        for username in self._excluded:
            r = self._excl_table.rowCount()
            self._excl_table.insertRow(r)
            self._excl_table.setItem(r, 0, QTableWidgetItem(username))

    def _collect_settings(self) -> dict:
        s = dict(self._settings)
        s["min_followers"] = self._f_min_followers.value()
        s["max_followers"] = self._f_max_followers.value()
        s["posts_per_tag"] = self._f_posts_per_tag.value()
        s["max_tags"]      = self._f_max_tags.value()
        for row, (key, _) in enumerate(_DELAY_STEPS):
            try:
                s[f"{key}_delay_min"] = float(self._delay_table.item(row, 1).text())
                s[f"{key}_delay_max"] = float(self._delay_table.item(row, 2).text())
            except (ValueError, AttributeError):
                pass
        return s

    def _collect_selectors(self) -> list[dict]:
        rows = []
        for r in range(self._sel_table.rowCount()):
            rows.append({
                "step_id":        (self._sel_table.item(r, 0) or QTableWidgetItem("")).text(),
                "step_name":      (self._sel_table.item(r, 1) or QTableWidgetItem("")).text(),
                "selector_type":  (self._sel_table.item(r, 2) or QTableWidgetItem("")).text(),
                "selector_value": (self._sel_table.item(r, 3) or QTableWidgetItem("")).text(),
            })
        return rows

    def _collect_excluded(self) -> list[str]:
        accounts = []
        for r in range(self._excl_table.rowCount()):
            item = self._excl_table.item(r, 0)
            if item:
                u = item.text().strip().lstrip("@")
                if u:
                    accounts.append(u)
        return accounts

    # ── Actions ───────────────────────────────────────────────────────────────

    def _save_all(self):
        try:
            storage.save_settings(self._collect_settings())
            storage.save_selectors(self._collect_selectors())
            storage.save_excluded(self._collect_excluded())
            self.back_requested.emit()
        except Exception as exc:
            QMessageBox.critical(self, "Save failed", str(exc))

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

    def _reset_selectors(self):
        defaults = storage.selector_defaults()
        self._sel_table.setRowCount(0)
        for row_data in defaults:
            r = self._sel_table.rowCount()
            self._sel_table.insertRow(r)
            step_id_item = QTableWidgetItem(row_data.get("step_id", ""))
            step_id_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self._sel_table.setItem(r, 0, step_id_item)
            self._sel_table.setItem(r, 1, QTableWidgetItem(row_data.get("step_name", "")))
            self._sel_table.setItem(r, 2, QTableWidgetItem(row_data.get("selector_type", "xpath")))
            self._sel_table.setItem(r, 3, QTableWidgetItem(row_data.get("selector_value", "")))

    def _run_pip(self):
        req = str(Path(__file__).parent.parent / "requirements.txt")
        self._pip_log.clear()
        self._process = QProcess(self)
        self._process.readyReadStandardOutput.connect(
            lambda: self._pip_log.append(
                self._process.readAllStandardOutput().data().decode(errors="replace")
            )
        )
        self._process.readyReadStandardError.connect(
            lambda: self._pip_log.append(
                self._process.readAllStandardError().data().decode(errors="replace")
            )
        )
        self._process.start(sys.executable, ["-m", "pip", "install", "-r", req])
