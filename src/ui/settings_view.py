"""SettingsView — QTabWidget 설정 화면 코디네이터.

탭별 로직은 `ui/settings/` 의 `*TabMixin` 으로 분리되어 있다.
이 클래스는 신호 정의 + __init__ + _build_ui + load/_populate + _save_all 만 담는
얇은 코디네이터다. 믹스인 메서드는 `self`(=SettingsView 인스턴스)에서 동작하며
`self._mapping_groups`/`self._flow_table` 등 위젯 속성을 그대로 세팅한다.
"""

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QMessageBox, QTabWidget,
)

import core.storage as storage
from ui.settings import (
    _as_bool,
    DelaysTabMixin, FlowTabMixin, TargetTabMixin,
    MappingTabMixin, ExcludedTabMixin,
    ConfigIOMixin,
)

# 테스트/외부 호환: `from ui.settings_view import _as_bool` 유지.
__all__ = ["SettingsView", "_as_bool"]


class SettingsView(
    QWidget,
    DelaysTabMixin, FlowTabMixin, TargetTabMixin,
    MappingTabMixin, ExcludedTabMixin,
    ConfigIOMixin,
):
    back_requested = pyqtSignal()
    imported = pyqtSignal()  # Import 완료 시 메인뷰 재로딩용

    def __init__(self, parent=None):
        super().__init__(parent)
        self._delays: dict = {}
        self._flow: dict = {}
        self._target: dict = {}
        self._selectors: list = []
        self._excluded: list = []
        self._process = None
        self._build_ui()

    # ── Public API ────────────────────────────────────────────────────────────

    def load(self):
        """Read all CSV files and populate UI fields."""
        self._delays     = storage.load_delays()
        self._flow       = storage.load_flow()
        self._target     = storage.load_target()
        self._selectors  = storage.load_selectors()
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

        btn_export = QPushButton("설정·데이터 내보내기")
        btn_export.setToolTip("선택한 항목(설정/제외명단/수집데이터)을 단일 .zip 으로 저장")
        btn_export.clicked.connect(self._export_config)
        hl.addWidget(btn_export)

        btn_import = QPushButton("불러오기")
        btn_import.setToolTip(".zip 에서 설정·데이터를 불러와 자동 적용")
        btn_import.clicked.connect(self._import_config)
        hl.addWidget(btn_import)

        btn_save = QPushButton("Save All")
        btn_save.setObjectName("btnPrimary")
        btn_save.clicked.connect(self._confirm_save)
        hl.addWidget(btn_save)

        root.addWidget(header)

        self._tabs = QTabWidget()
        self._tabs.addTab(self._build_target_tab(),   "타겟")
        self._tabs.addTab(self._build_delays_tab(),   "딜레이")
        self._tabs.addTab(self._build_flow_tab(),     "수집 설정")
        self._tabs.addTab(self._build_excluded_tab(), "제외 계정")
        self._tabs.addTab(self._build_mapping_tab(),  "버튼매핑")
        root.addWidget(self._tabs)

    # ── Populate ───────────────────────────────────────────────────────────────

    def _populate(self):
        self._populate_delays(self._delays)
        self._populate_flow(self._flow)
        self._populate_target(self._target)
        self._populate_mapping(self._selectors)
        self._populate_excluded(self._excluded)

    # ── Actions ───────────────────────────────────────────────────────────────

    def _confirm_save(self):
        """[Save All] 클릭 시 저장 확인 모달 → [예]일 때만 실제 저장."""
        reply = QMessageBox.question(
            self, "설정 저장", "변경한 설정을 저장하시겠습니까?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._save_all()

    def _save_all(self):
        try:
            storage.save_delays(self._collect_delays())
            storage.save_flow(self._collect_flow())
            storage.save_target(self._collect_target())
            storage.save_excluded(self._collect_excluded())
            storage.save_selectors(self._collect_selectors())
            self.back_requested.emit()
        except Exception as exc:
            QMessageBox.critical(self, "Save failed", str(exc))
