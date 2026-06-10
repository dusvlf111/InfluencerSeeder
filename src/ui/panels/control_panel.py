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
    resume_requested = pyqtSignal()      # [이어하기] (state.json 기반 재개, §7)
    stop_requested = pyqtSignal()        # [정지] 버튼
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

        # 액션 버튼 (시작/정지)
        row1 = QHBoxLayout()
        self._btn_start = QPushButton("수집 시작")
        self._btn_start.setObjectName("btnPrimary")
        self._btn_start.clicked.connect(self._on_start)
        self._btn_stop = QPushButton("정지")
        self._btn_stop.setObjectName("btnDanger")
        self._btn_stop.setEnabled(False)
        self._btn_stop.clicked.connect(self.stop_requested)
        row1.addWidget(self._btn_start)
        row1.addWidget(self._btn_stop)
        layout.addLayout(row1)

        # 이어하기 / 초기화
        row2 = QHBoxLayout()
        self._btn_resume = QPushButton("이어하기")
        self._btn_resume.setEnabled(False)
        self._btn_resume.clicked.connect(self.resume_requested)
        self._btn_reset = QPushButton("초기화")
        self._btn_reset.clicked.connect(self.reset_requested)
        row2.addWidget(self._btn_resume)
        row2.addWidget(self._btn_reset)
        layout.addLayout(row2)

        # 제외 계정
        self.excluded_widget = ExcludedAccountsWidget()
        layout.addWidget(self.excluded_widget)

        # 설정 버튼
        btn_settings = QPushButton("설정")
        btn_settings.clicked.connect(self.settings_requested)
        layout.addWidget(btn_settings)

        layout.addStretch()

    def _apply_saved_settings(self):
        # 검색 조건(모드/검색어/팔로워 범위)의 단일 출처는 target.csv —
        # 설정 화면의 '타겟' 탭과 양방향으로 공유된다.
        self.apply_target(storage.load_target())

    def apply_target(self, target: dict):
        """target.csv(dict) 값을 검색 모드/검색어/팔로워 범위 위젯에 반영."""
        mode = str(target.get("mode", "hashtag") or "hashtag")
        if mode == "keyword":
            self._btn_keyword.setChecked(True)
        else:
            self._btn_hashtag.setChecked(True)
        self._on_mode_change()
        self._search_input.setText(str(target.get("keyword", "") or ""))
        self._follower_filter.set_values(
            int(target.get("min_followers", 0) or 0),
            int(target.get("max_followers", 0) or 0),
        )

    def current_target(self) -> dict:
        """현재 컨트롤 패널 검색 조건을 target.csv 부분 dict 로 반환(양방향 동기화).

        타겟 전용 필드(팔로잉 범위/최소 게시물)는 설정 탭에서만 편집하므로 포함하지
        않는다 — 호출부가 기존 target.csv 와 병합한다."""
        return {
            "mode": "hashtag" if self._btn_hashtag.isChecked() else "keyword",
            "keyword": self._search_input.text().strip(),
            "min_followers": self._follower_filter.min_followers,
            "max_followers": self._follower_filter.max_followers,
        }

    def reload_excluded(self):
        """제외 계정 목록을 excluded.csv 에서 다시 읽어 표시 갱신(설정 편집 반영)."""
        self.excluded_widget.refresh_from_storage()

    def _on_mode_change(self):
        if self._btn_hashtag.isChecked():
            self._search_label.setText("해시태그 (#없이 입력)")
            self._search_input.setPlaceholderText("예: 취준생, 인턴")
        else:
            self._search_label.setText("캡션 키워드")
            self._search_input.setPlaceholderText("예: 취업 준비, 인턴십")

    def collect_params(self) -> dict | None:
        """현재 입력값으로 ScraperThread params dict 구성.

        검색어가 비면 None (시작 불가). [이어하기]/[시작] 양쪽에서 재사용.
        """
        term = self._search_input.text().strip()
        if not term:
            return None
        s = storage.load_settings()
        # v3: selectors 는 priority-체인 list[dict] (storage.load_selectors).
        # ScraperThread 생성자가 list 형태를 직접 받는다.
        return {
            "mode": "hashtag" if self._btn_hashtag.isChecked() else "keyword",
            "search_term": term,
            "count": self._count_spin.value(),
            "min_followers": self._follower_filter.min_followers,
            "max_followers": self._follower_filter.max_followers,
            "excluded_set": set(self.excluded_widget.accounts),
            "selectors": storage.load_selectors(),
            "app_settings": s,
        }

    def _on_start(self):
        params = self.collect_params()
        if params is None:
            return
        self.start_requested.emit(params)

    def set_resume_available(self, available: bool):
        """state.json 존재 여부로 [이어하기] 활성화 (§7)."""
        self._btn_resume.setEnabled(bool(available))

    def set_running(self, running: bool, waiting_login: bool = False):
        # Login confirmation is handled solely by LoginWaitDialog now; the
        # ``waiting_login`` flag is accepted for signal compatibility but no
        # longer toggles an in-panel button.
        self._btn_start.setEnabled(not running)
        self._btn_stop.setEnabled(running)
        self._btn_resume.setEnabled(self._btn_resume.isEnabled() and not running)
