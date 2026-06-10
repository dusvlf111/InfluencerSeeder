import sys
from pathlib import Path

from PyQt6.QtCore import QProcess, pyqtSignal, Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QGroupBox, QFormLayout, QSpinBox,
    QDoubleSpinBox, QTextEdit, QFrame, QMessageBox,
    QTabWidget, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QLineEdit,
    QComboBox, QCheckBox,
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
]

_BROWSERS = ["chrome", "edge", "firefox"]
_MODES = ["hashtag", "keyword"]


def _as_bool(v) -> bool:
    """storage 의 bool 값은 문자열('true'/'false')로 로드된다 — 통일 해석."""
    return str(v).strip().lower() == "true"


class SettingsView(QWidget):
    back_requested = pyqtSignal()
    imported = pyqtSignal()  # Import 완료 시 메인뷰 재로딩용(flow-builder/Push4 연결)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._settings: dict = {}
        self._web: dict = {}
        self._delays: dict = {}
        self._flow: dict = {}
        self._target: dict = {}
        self._selectors: list = []
        self._excluded: list = []
        self._process: QProcess | None = None
        self._build_ui()

    # ── Public API ────────────────────────────────────────────────────────────

    def load(self):
        """Read all CSV files and populate UI fields."""
        self._settings  = storage.load_settings()
        self._web       = storage.load_web()
        self._delays    = storage.load_delays()
        self._flow      = storage.load_flow()
        self._target    = storage.load_target()
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

        # Tab widget — 기본 설정 그룹 탭 (웹/시간텀/플로우/타겟/제외) + 기존 Selectors 유지.
        # ⚠️ Selectors 탭은 flow-builder(P3)가 카드형으로 교체 예정 — 여기서 손대지 않는다.
        self._tabs = QTabWidget()
        self._tabs.addTab(self._build_web_tab(),       "Web")
        self._tabs.addTab(self._build_delays_tab(),    "Delays")
        self._tabs.addTab(self._build_flow_tab(),      "Flow")
        self._tabs.addTab(self._build_target_tab(),    "Target")
        self._tabs.addTab(self._build_excluded_tab(),  "Excluded")
        self._tabs.addTab(self._build_selectors_tab(), "Selectors")
        self._tabs.addTab(self._build_deps_tab(),      "Dependencies")
        root.addWidget(self._tabs)

    # ── Tab: Web (§2.1) ────────────────────────────────────────────────────────

    def _build_web_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setSpacing(12)
        form.setContentsMargins(28, 20, 28, 20)

        self._w_browser = QComboBox()
        self._w_browser.addItems(_BROWSERS)
        form.addRow("Browser", self._w_browser)

        self._w_headless = QCheckBox("Run browser without a window")
        form.addRow("Headless", self._w_headless)

        self._w_window_width = QSpinBox()
        self._w_window_width.setRange(320, 7680)
        self._w_window_width.setSingleStep(10)
        form.addRow("Window width", self._w_window_width)

        self._w_window_height = QSpinBox()
        self._w_window_height.setRange(320, 4320)
        self._w_window_height.setSingleStep(10)
        form.addRow("Window height", self._w_window_height)

        self._w_randomize_window = QCheckBox("Randomize window size per run")
        form.addRow("Randomize window", self._w_randomize_window)

        self._w_randomize_user_agent = QCheckBox("Randomize user agent per run")
        form.addRow("Randomize user agent", self._w_randomize_user_agent)

        self._w_user_data_dir = QLineEdit()
        self._w_user_data_dir.setPlaceholderText("(blank = temporary profile)")
        form.addRow("User data dir", self._w_user_data_dir)

        self._w_locale = QLineEdit()
        self._w_locale.setPlaceholderText("ko-KR")
        form.addRow("Locale", self._w_locale)

        self._w_implicit_wait = QSpinBox()
        self._w_implicit_wait.setRange(0, 120)
        form.addRow("Implicit wait (sec)", self._w_implicit_wait)

        self._w_page_load_timeout = QSpinBox()
        self._w_page_load_timeout.setRange(0, 600)
        form.addRow("Page load timeout (sec)", self._w_page_load_timeout)

        return w

    # ── Tab: Delays (시간텀, §2.3) ─────────────────────────────────────────────

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

    # ── Tab: Flow (§2.4) ───────────────────────────────────────────────────────

    def _build_flow_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setSpacing(12)
        form.setContentsMargins(28, 20, 28, 20)

        self._fl_max_tags = QSpinBox()
        self._fl_max_tags.setRange(1, 50)
        self._fl_max_tags.setToolTip(
            "How many tag suggestions to cycle through.\n"
            "Search is re-run for each subsequent suggestion."
        )
        form.addRow("Max tag suggestions", self._fl_max_tags)

        self._fl_tag_start_index = QSpinBox()
        self._fl_tag_start_index.setRange(0, 49)
        form.addRow("Tag start index", self._fl_tag_start_index)

        self._fl_posts_per_tag = QSpinBox()
        self._fl_posts_per_tag.setRange(1, 200)
        self._fl_posts_per_tag.setToolTip("Posts to collect per tag suggestion")
        form.addRow("Posts per tag", self._fl_posts_per_tag)

        self._fl_scroll_max_attempts = QSpinBox()
        self._fl_scroll_max_attempts.setRange(0, 200)
        form.addRow("Scroll max attempts", self._fl_scroll_max_attempts)

        self._fl_skip_visited_profile = QCheckBox("Skip profiles already collected")
        form.addRow("Skip visited profile", self._fl_skip_visited_profile)

        self._fl_stop_on_consecutive_miss = QSpinBox()
        self._fl_stop_on_consecutive_miss.setRange(0, 1000)
        self._fl_stop_on_consecutive_miss.setToolTip(
            "Stop a tag after this many consecutive duplicate/filtered posts (0 = never)."
        )
        form.addRow("Stop on consecutive miss", self._fl_stop_on_consecutive_miss)

        return w

    # ── Tab: Target (§2.5) ─────────────────────────────────────────────────────

    def _build_target_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setSpacing(12)
        form.setContentsMargins(28, 20, 28, 20)

        self._t_min_followers = QSpinBox()
        self._t_min_followers.setRange(0, 100_000_000)
        self._t_min_followers.setSingleStep(1000)
        form.addRow("Min followers (0 = no limit)", self._t_min_followers)

        self._t_max_followers = QSpinBox()
        self._t_max_followers.setRange(0, 100_000_000)
        self._t_max_followers.setSingleStep(1000)
        form.addRow("Max followers (0 = no limit)", self._t_max_followers)

        self._t_min_following = QSpinBox()
        self._t_min_following.setRange(0, 100_000_000)
        self._t_min_following.setSingleStep(100)
        form.addRow("Min following (0 = no limit)", self._t_min_following)

        self._t_max_following = QSpinBox()
        self._t_max_following.setRange(0, 100_000_000)
        self._t_max_following.setSingleStep(100)
        form.addRow("Max following (0 = no limit)", self._t_max_following)

        self._t_min_posts = QSpinBox()
        self._t_min_posts.setRange(0, 1_000_000)
        form.addRow("Min posts (0 = no limit)", self._t_min_posts)

        self._t_keyword = QLineEdit()
        self._t_keyword.setPlaceholderText("hashtag or keyword to search")
        form.addRow("Keyword", self._t_keyword)

        self._t_mode = QComboBox()
        self._t_mode.addItems(_MODES)
        form.addRow("Mode", self._t_mode)

        return w

    # ── Tab: Selectors ──────────────────────────────────────────────────────────
    # ⚠️ flow-builder(P3) 영역 — 구조/collect/save 를 변경하지 말 것.

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

    # ── Populate (그룹별) ───────────────────────────────────────────────────────

    def _populate(self):
        self._populate_web(self._web)
        self._populate_delays(self._delays)
        self._populate_flow(self._flow)
        self._populate_target(self._target)
        self._populate_selectors(self._selectors)
        self._populate_excluded(self._excluded)

    def _populate_web(self, web: dict):
        browser = str(web.get("browser", "chrome"))
        idx = self._w_browser.findText(browser)
        self._w_browser.setCurrentIndex(idx if idx >= 0 else 0)
        self._w_headless.setChecked(_as_bool(web.get("headless", "false")))
        self._w_window_width.setValue(int(web.get("window_width", 1280)))
        self._w_window_height.setValue(int(web.get("window_height", 900)))
        self._w_randomize_window.setChecked(_as_bool(web.get("randomize_window", "true")))
        self._w_randomize_user_agent.setChecked(_as_bool(web.get("randomize_user_agent", "true")))
        self._w_user_data_dir.setText(str(web.get("user_data_dir", "") or ""))
        self._w_locale.setText(str(web.get("locale", "ko-KR")))
        self._w_implicit_wait.setValue(int(web.get("implicit_wait", 5)))
        self._w_page_load_timeout.setValue(int(web.get("page_load_timeout", 30)))

    def _populate_delays(self, delays: dict):
        for row, (key, _) in enumerate(_DELAY_STEPS):
            lo, hi = delays.get(key, (1.0, 2.0))
            self._delay_table.item(row, 1).setText(str(lo))
            self._delay_table.item(row, 2).setText(str(hi))

    def _populate_flow(self, flow: dict):
        self._fl_max_tags.setValue(int(flow.get("max_tags", 3)))
        self._fl_tag_start_index.setValue(int(flow.get("tag_start_index", 0)))
        self._fl_posts_per_tag.setValue(int(flow.get("posts_per_tag", 5)))
        self._fl_scroll_max_attempts.setValue(int(flow.get("scroll_max_attempts", 15)))
        self._fl_skip_visited_profile.setChecked(_as_bool(flow.get("skip_visited_profile", "true")))
        self._fl_stop_on_consecutive_miss.setValue(int(flow.get("stop_on_consecutive_miss", 10)))

    def _populate_target(self, target: dict):
        self._t_min_followers.setValue(int(target.get("min_followers", 0)))
        self._t_max_followers.setValue(int(target.get("max_followers", 0)))
        self._t_min_following.setValue(int(target.get("min_following", 0)))
        self._t_max_following.setValue(int(target.get("max_following", 0)))
        self._t_min_posts.setValue(int(target.get("min_posts", 0)))
        self._t_keyword.setText(str(target.get("keyword", "") or ""))
        mode = str(target.get("mode", "hashtag"))
        idx = self._t_mode.findText(mode)
        self._t_mode.setCurrentIndex(idx if idx >= 0 else 0)

    def _populate_selectors(self, selectors: list):
        self._sel_table.setRowCount(0)
        for row_data in selectors:
            r = self._sel_table.rowCount()
            self._sel_table.insertRow(r)
            step_id_item = QTableWidgetItem(row_data.get("step_id", ""))
            step_id_item.setFlags(Qt.ItemFlag.ItemIsEnabled)  # read-only
            self._sel_table.setItem(r, 0, step_id_item)
            self._sel_table.setItem(r, 1, QTableWidgetItem(row_data.get("step_name", "")))
            self._sel_table.setItem(r, 2, QTableWidgetItem(row_data.get("selector_type", "xpath")))
            self._sel_table.setItem(r, 3, QTableWidgetItem(row_data.get("selector_value", "")))

    def _populate_excluded(self, excluded: list):
        self._excl_table.setRowCount(0)
        for username in excluded:
            r = self._excl_table.rowCount()
            self._excl_table.insertRow(r)
            self._excl_table.setItem(r, 0, QTableWidgetItem(username))

    # ── Collect (그룹별) ────────────────────────────────────────────────────────

    def _collect_web(self) -> dict:
        return {
            "browser":              self._w_browser.currentText(),
            "headless":             "true" if self._w_headless.isChecked() else "false",
            "window_width":         self._w_window_width.value(),
            "window_height":        self._w_window_height.value(),
            "randomize_window":     "true" if self._w_randomize_window.isChecked() else "false",
            "randomize_user_agent": "true" if self._w_randomize_user_agent.isChecked() else "false",
            "user_data_dir":        self._w_user_data_dir.text().strip(),
            "locale":               self._w_locale.text().strip() or "ko-KR",
            "implicit_wait":        self._w_implicit_wait.value(),
            "page_load_timeout":    self._w_page_load_timeout.value(),
        }

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

    def _collect_flow(self) -> dict:
        return {
            "max_tags":                 self._fl_max_tags.value(),
            "tag_start_index":          self._fl_tag_start_index.value(),
            "posts_per_tag":            self._fl_posts_per_tag.value(),
            "scroll_max_attempts":      self._fl_scroll_max_attempts.value(),
            "skip_visited_profile":     "true" if self._fl_skip_visited_profile.isChecked() else "false",
            "stop_on_consecutive_miss": self._fl_stop_on_consecutive_miss.value(),
        }

    def _collect_target(self) -> dict:
        return {
            "min_followers": self._t_min_followers.value(),
            "max_followers": self._t_max_followers.value(),
            "min_following": self._t_min_following.value(),
            "max_following": self._t_max_following.value(),
            "min_posts":     self._t_min_posts.value(),
            "keyword":       self._t_keyword.text().strip(),
            "mode":          self._t_mode.currentText(),
        }

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
            storage.save_web(self._collect_web())
            storage.save_delays(self._collect_delays())
            storage.save_flow(self._collect_flow())
            storage.save_target(self._collect_target())
            storage.save_excluded(self._collect_excluded())
            # 셀렉터/레거시 settings 는 기존 동작 유지 (flow-builder 영역).
            storage.save_selectors(self._collect_selectors())
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
