from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QLineEdit, QSpinBox,
    QGroupBox, QButtonGroup,
)

from ui.widgets.follower_filter import FollowerFilterWidget
from ui.widgets.excluded_widget import ExcludedAccountsWidget
import core.storage as storage


class ControlPanel(QWidget):
    """좌측 컨트롤 패널 — 검색 설정, 필터, 제외 계정, 버튼."""

    start_requested = pyqtSignal(dict)   # 수집 파라미터 dict
    login_done_requested = pyqtSignal()
    reset_requested = pyqtSignal()
    settings_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(340)
        self._build_ui()
        self._apply_saved_settings()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 12, 16)

        # 로고
        logo = QLabel("인플루언서 시딩기")
        logo.setObjectName("labelAccent")
        logo.setFont(QFont("", 16, QFont.Weight.Bold))
        layout.addWidget(logo)

        # 모드 토글
        mode_box = QGroupBox("검색 모드")
        mode_layout = QHBoxLayout(mode_box)
        self._btn_hashtag = QPushButton("# 해시태그")
        self._btn_hashtag.setCheckable(True)
        self._btn_hashtag.setChecked(True)
        self._btn_keyword = QPushButton("캡션 키워드")
        self._btn_keyword.setCheckable(True)
        self._mode_group = QButtonGroup(self)
        self._mode_group.setExclusive(True)
        self._mode_group.addButton(self._btn_hashtag)
        self._mode_group.addButton(self._btn_keyword)
        self._mode_group.buttonClicked.connect(self._on_mode_change)
        mode_layout.addWidget(self._btn_hashtag)
        mode_layout.addWidget(self._btn_keyword)
        layout.addWidget(mode_box)

        # 검색어
        search_box = QGroupBox("검색어")
        search_layout = QVBoxLayout(search_box)
        self._search_label = QLabel("해시태그 (#없이 입력)")
        self._search_label.setObjectName("labelMuted")
        search_layout.addWidget(self._search_label)
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("예: 취준생, 인턴")
        search_layout.addWidget(self._search_input)
        layout.addWidget(search_box)

        # 수집 설정
        settings_box = QGroupBox("수집 설정")
        settings_grid = QGridLayout(settings_box)
        settings_grid.setSpacing(8)
        settings_grid.addWidget(QLabel("수집 수"), 0, 0)
        self._count_spin = QSpinBox()
        self._count_spin.setRange(5, 200)
        self._count_spin.setValue(20)
        settings_grid.addWidget(self._count_spin, 0, 1)
        settings_grid.addWidget(QLabel("팔로워 범위"), 1, 0)
        self._follower_filter = FollowerFilterWidget()
        settings_grid.addWidget(self._follower_filter, 1, 1)
        layout.addWidget(settings_box)

        # 액션 버튼
        btn_row = QHBoxLayout()
        self._btn_start = QPushButton("수집 시작")
        self._btn_start.setObjectName("btnPrimary")
        self._btn_start.clicked.connect(self._on_start)
        self._btn_login_done = QPushButton("로그인 완료")
        self._btn_login_done.setObjectName("btnSuccess")
        self._btn_login_done.setEnabled(False)
        self._btn_login_done.clicked.connect(self.login_done_requested)
        self._btn_reset = QPushButton("초기화")
        self._btn_reset.clicked.connect(self.reset_requested)
        btn_row.addWidget(self._btn_start)
        btn_row.addWidget(self._btn_login_done)
        btn_row.addWidget(self._btn_reset)
        layout.addLayout(btn_row)

        # 제외 계정
        self.excluded_widget = ExcludedAccountsWidget()
        layout.addWidget(self.excluded_widget)

        # 설정 버튼
        btn_settings = QPushButton("설정")
        btn_settings.clicked.connect(self.settings_requested)
        layout.addWidget(btn_settings)

        layout.addStretch()

    def _apply_saved_settings(self):
        s = storage.load_settings()
        self._follower_filter.set_values(
            s.get("min_followers", 0),
            s.get("max_followers", 0),
        )

    def _on_mode_change(self):
        if self._btn_hashtag.isChecked():
            self._search_label.setText("해시태그 (#없이 입력)")
            self._search_input.setPlaceholderText("예: 취준생, 인턴")
        else:
            self._search_label.setText("캡션 키워드")
            self._search_input.setPlaceholderText("예: 취업 준비, 인턴십")

    def _on_start(self):
        term = self._search_input.text().strip()
        if not term:
            return
        s = storage.load_settings()
        from core.storage import selector_defaults
        sel_keys = set(selector_defaults().keys())
        self.start_requested.emit({
            "mode": "hashtag" if self._btn_hashtag.isChecked() else "keyword",
            "search_term": term,
            "count": self._count_spin.value(),
            "min_followers": self._follower_filter.min_followers,
            "max_followers": self._follower_filter.max_followers,
            "excluded_set": set(self.excluded_widget.accounts),
            "selectors": {k: v for k, v in s.items() if k in sel_keys},
            "app_settings": s,
        })

    def set_running(self, running: bool, waiting_login: bool = False):
        self._btn_start.setEnabled(not running)
        self._btn_login_done.setEnabled(waiting_login)
