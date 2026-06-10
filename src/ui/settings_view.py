import sys
from pathlib import Path

from PyQt6.QtCore import QProcess, pyqtSignal, Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QGroupBox, QFormLayout, QSpinBox,
    QDoubleSpinBox, QTextEdit, QFrame, QMessageBox,
    QTabWidget, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QLineEdit,
    QComboBox, QCheckBox, QScrollArea, QFileDialog,
)

import core.storage as storage
from core.assets import guide_image_for_selector

# Guide text shown on every button-mapping card.
_MAPPING_GUIDE = (
    "브라우저에서 요소 우클릭 → 검사(Inspect) → 강조된 요소 우클릭 → "
    "Copy → Copy XPath(또는 Copy selector) → 아래 값 칸에 붙여넣기.  "
    "type 은 xpath / css / coord."
)

# Selector-table columns for each mapping card.
_SEL_COLS = ["priority", "type", "value"]

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
        self._flow_steps: list = []
        self._excluded: list = []
        # step_id (declaration order) → its selector candidate QTableWidget.
        self._mapping_tables: dict[str, QTableWidget] = {}
        self._mapping_names: dict[str, str] = {}
        self._process: QProcess | None = None
        self._build_ui()

    # ── Public API ────────────────────────────────────────────────────────────

    def load(self):
        """Read all CSV files and populate UI fields."""
        self._settings   = storage.load_settings()
        self._web        = storage.load_web()
        self._delays     = storage.load_delays()
        self._flow       = storage.load_flow()
        self._target     = storage.load_target()
        self._selectors  = storage.load_selectors()
        self._flow_steps = storage.load_flow_steps()
        self._excluded   = storage.load_excluded()
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

        btn_export = QPushButton("설정 내보내기")
        btn_export.clicked.connect(self._export_config)
        hl.addWidget(btn_export)

        btn_import = QPushButton("설정 불러오기")
        btn_import.clicked.connect(self._import_config)
        hl.addWidget(btn_import)

        btn_save = QPushButton("Save All")
        btn_save.setObjectName("btnPrimary")
        btn_save.clicked.connect(self._save_all)
        hl.addWidget(btn_save)

        root.addWidget(header)

        # Tab widget — 기본 설정 그룹 탭 (웹/시간텀/플로우/타겟/제외)
        # + 버튼매핑(셀렉터 카드, P3) + 플로우 빌더(P4) + 의존성.
        self._tabs = QTabWidget()
        self._tabs.addTab(self._build_web_tab(),       "Web")
        self._tabs.addTab(self._build_delays_tab(),    "Delays")
        self._tabs.addTab(self._build_flow_tab(),      "Flow")
        self._tabs.addTab(self._build_target_tab(),    "Target")
        self._tabs.addTab(self._build_excluded_tab(),  "Excluded")
        self._tabs.addTab(self._build_mapping_tab(),   "버튼매핑")
        self._tabs.addTab(self._build_flowbuilder_tab(), "플로우")
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

    # ── Tab: 버튼매핑 (P3 — 스크린샷 + XPath 가이드 + 셀렉터 후보 표) ────────────────
    #
    # selectors.csv 의 step_id 별로 카드(QScrollArea)를 만든다: 상단에 가이드 스크린샷,
    # 그 아래 "XPath 복사하는 법" 설명, 그 아래 해당 step 의 셀렉터 후보 표
    # (priority/type/value 행 추가·삭제·정렬). 저장 데이터 계약은 기존
    # save_selectors(list[dict] with priority int) 를 그대로 유지한다.

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
                    pix.scaledToWidth(360, Qt.TransformationMode.SmoothTransformation)
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

    # ── Tab: 플로우 빌더 (P4 — order/phase/step_name/action/selector_ref/param/enabled) ─

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
        self._populate_mapping(self._selectors)
        self._populate_flow_steps(self._flow_steps)
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

    def _populate_flow_steps(self, flow_steps: list):
        self._flow_table.setRowCount(0)
        for row_data in flow_steps:
            self._flow_insert_step_row(self._flow_table.rowCount(), row_data)
        self._flow_renumber()

    def _populate_excluded(self, excluded: list):
        self._excl_table.setRowCount(0)
        for username in excluded:
            r = self._excl_table.rowCount()
            self._excl_table.insertRow(r)
            self._excl_table.setItem(r, 0, QTableWidgetItem(username))

    # ── 버튼매핑 카드 표 조작 (P3) ──────────────────────────────────────────────────

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

    # ── 플로우 빌더 표 조작 (P4) ──────────────────────────────────────────────────

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

    def _collect_flow_steps(self) -> list[dict]:
        rows: list[dict] = []
        for r in range(self._flow_table.rowCount()):
            rows.append(self._flow_collect_row(r))
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
            # 버튼매핑(셀렉터 후보) — save_selectors 데이터 계약(priority int) 유지.
            storage.save_selectors(self._collect_selectors())
            # 플로우 빌더(P4) — flow_steps.csv.
            storage.save_flow_steps(self._collect_flow_steps())
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

    # ── 설정 CSV 폴더 가져오기/내보내기 (P5) ────────────────────────────────────────

    def _export_config(self):
        directory = QFileDialog.getExistingDirectory(self, "설정 내보내기 — 폴더 선택")
        if not directory:
            return
        try:
            written = storage.export_config_to_dir(directory)
        except Exception as exc:
            QMessageBox.critical(self, "내보내기 실패", str(exc))
            return
        if written:
            QMessageBox.information(
                self, "설정 내보내기 완료",
                "다음 파일을 내보냈습니다:\n\n" + "\n".join(written),
            )
        else:
            QMessageBox.warning(self, "설정 내보내기", "내보낼 설정 파일이 없습니다.")

    def _import_config(self):
        directory = QFileDialog.getExistingDirectory(self, "설정 불러오기 — 폴더 선택")
        if not directory:
            return
        try:
            imported = storage.import_config_from_dir(directory)
        except Exception as exc:
            QMessageBox.critical(self, "불러오기 실패", str(exc))
            return
        if imported:
            self.load()              # 반영된 CSV 로 UI 갱신
            self.imported.emit()     # 메인뷰 재로딩 신호
            QMessageBox.information(
                self, "설정 불러오기 완료",
                "다음 파일을 반영했습니다:\n\n" + "\n".join(imported),
            )
        else:
            QMessageBox.warning(
                self, "설정 불러오기",
                "선택한 폴더에서 인식 가능한 설정 CSV 를 찾지 못했습니다.",
            )

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
