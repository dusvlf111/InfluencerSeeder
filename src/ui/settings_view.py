"""SettingsView — QTabWidget 설정 화면 코디네이터.

탭별 로직은 `ui/settings/` 의 `*TabMixin` 으로 분리되어 있다(990줄 → 믹스인).
이 클래스는 신호 정의 + __init__ + _build_ui + load/_populate + _save_all 만 담는
얇은 코디네이터다. 믹스인 메서드는 `self`(=SettingsView 인스턴스)에서 동작하며
`self._w_browser`/`self._flow_table` 등 위젯 속성을 그대로 세팅한다.
"""

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QMessageBox, QTabWidget,
)

import core.storage as storage
from ui.settings import (
    _as_bool,
    WebTabMixin, DelaysTabMixin, FlowTabMixin, TargetTabMixin,
    MappingTabMixin, FieldsTabMixin, FlowBuilderTabMixin, ExcludedTabMixin,
    DepsTabMixin, ConfigIOMixin,
)

# 테스트/외부 호환: `from ui.settings_view import _as_bool` 유지.
__all__ = ["SettingsView", "_as_bool"]


class SettingsView(
    QWidget,
    WebTabMixin, DelaysTabMixin, FlowTabMixin, TargetTabMixin,
    MappingTabMixin, FieldsTabMixin, FlowBuilderTabMixin, ExcludedTabMixin,
    DepsTabMixin, ConfigIOMixin,
):
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
        self._fields: dict = {}
        self._process = None
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
        self._fields     = storage.load_fields()
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

        btn_export = QPushButton("폴더로 내보내기")
        btn_export.setToolTip("선택한 폴더에 설정 CSV들을 각각 저장")
        btn_export.clicked.connect(self._export_config)
        hl.addWidget(btn_export)

        btn_export_file = QPushButton("파일로 내보내기")
        btn_export_file.setToolTip("설정 전체를 단일 .zip 파일로 저장 (공유용)")
        btn_export_file.clicked.connect(self._export_config_file)
        hl.addWidget(btn_export_file)

        btn_import = QPushButton("폴더에서 불러오기")
        btn_import.clicked.connect(self._import_config)
        hl.addWidget(btn_import)

        btn_import_file = QPushButton("파일에서 불러오기")
        btn_import_file.setToolTip(".zip 설정 파일에서 불러오기")
        btn_import_file.clicked.connect(self._import_config_file)
        hl.addWidget(btn_import_file)

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
        self._tabs.addTab(self._build_fields_tab(),    "수집 항목")
        self._tabs.addTab(self._build_mapping_tab(),   "버튼매핑")
        self._tabs.addTab(self._build_flowbuilder_tab(), "플로우")
        self._tabs.addTab(self._build_deps_tab(),      "Dependencies")
        root.addWidget(self._tabs)

    # ── Populate (그룹별) ───────────────────────────────────────────────────────

    def _populate(self):
        self._populate_web(self._web)
        self._populate_delays(self._delays)
        self._populate_flow(self._flow)
        self._populate_target(self._target)
        self._populate_fields(self._fields)
        self._populate_mapping(self._selectors)
        self._populate_flow_steps(self._flow_steps)
        self._populate_excluded(self._excluded)

    # ── Actions ───────────────────────────────────────────────────────────────

    def _save_all(self):
        try:
            storage.save_web(self._collect_web())
            storage.save_delays(self._collect_delays())
            storage.save_flow(self._collect_flow())
            storage.save_target(self._collect_target())
            storage.save_excluded(self._collect_excluded())
            # 수집 항목(Fix-2 B) — fields.csv.
            storage.save_fields(self._collect_fields_settings())
            # 버튼매핑(셀렉터 후보) — save_selectors 데이터 계약(priority int) 유지.
            storage.save_selectors(self._collect_selectors())
            # 플로우 빌더(P4) — flow_steps.csv.
            storage.save_flow_steps(self._collect_flow_steps())
            self.back_requested.emit()
        except Exception as exc:
            QMessageBox.critical(self, "Save failed", str(exc))
