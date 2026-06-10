from pathlib import Path

from PyQt6.QtCore import Qt, QUrl, QTimer, pyqtSignal
from PyQt6.QtGui import QCursor, QDesktopServices
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFrame,
    QLabel, QPushButton, QProgressBar, QTextEdit,
    QTableWidget, QTableWidgetItem, QTabWidget,
    QGroupBox, QHeaderView, QAbstractItemView,
    QFileDialog, QMessageBox,
)

from design.tokens import Colors as C
import core.storage as storage


class ResultsPanel(QWidget):
    """Right panel — progress, results table, log."""

    login_done_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._results: list[dict] = []
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(12, 16, 16, 16)

        # Progress group
        pg_box = QGroupBox("Progress")
        pb_layout = QVBoxLayout(pg_box)
        pb_layout.setSpacing(4)
        self._step_label = QLabel("Waiting to start")
        self._step_label.setObjectName("labelMuted")
        pb_layout.addWidget(self._step_label)
        self._progress_bar = QProgressBar()
        self._progress_bar.setValue(0)
        pb_layout.addWidget(self._progress_bar)
        # 진행 표시 라벨: 현재 step · 수집 N · 중복skip M (§8)
        self._progress_label = QLabel("")
        self._progress_label.setObjectName("labelMuted")
        pb_layout.addWidget(self._progress_label)
        layout.addWidget(pg_box)

        self._cur_step = ""
        self._skip_count = 0
        self._update_progress_label()

        # Tabs
        self._tabs = QTabWidget()
        self._tabs.addTab(self._build_results_tab(), "Results")
        self._tabs.addTab(self._build_log_tab(), "Log")
        layout.addWidget(self._tabs)

    def _build_results_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        toolbar = QHBoxLayout()
        self._count_label = QLabel("0 collected")
        self._count_label.setObjectName("labelMuted")
        btn_import = QPushButton("Import CSV")
        btn_import.clicked.connect(self._import_csv)
        btn_export = QPushButton("Export CSV")
        btn_export.clicked.connect(self._export_csv)
        toolbar.addWidget(self._count_label)
        toolbar.addStretch()
        toolbar.addWidget(btn_import)
        toolbar.addWidget(btn_export)
        layout.addLayout(toolbar)

        # 컬럼: # | 유저네임 | 팔로워 | 팔로잉 | 게시물 | 소개 | 링크
        self._table = QTableWidget(0, 7)
        self._table.setObjectName("resultsTable")
        self._table.setHorizontalHeaderLabels(
            ["#", "유저네임", "팔로워", "팔로잉", "게시물", "소개", "링크"]
        )
        hh = self._table.horizontalHeader()
        hh.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)         # 소개
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)  # 유저네임
        hh.setHighlightSections(False)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setAlternatingRowColors(True)
        self._table.setShowGrid(False)
        self._table.verticalHeader().setVisible(False)
        self._table.verticalHeader().setDefaultSectionSize(34)   # 넉넉한 행 높이
        self._table.setColumnWidth(0, 36)
        self._table.setColumnWidth(2, 84)
        self._table.setColumnWidth(3, 72)
        self._table.setColumnWidth(4, 64)
        self._table.setColumnWidth(6, 56)
        self._table.cellDoubleClicked.connect(self._on_cell_double_clicked)
        self._table.setMouseTracking(True)
        self._table.viewport().setMouseTracking(True)
        self._table.cellEntered.connect(self._on_cell_hovered)

        self._hover_timer = QTimer(self)
        self._hover_timer.setSingleShot(True)
        self._hover_timer.setInterval(400)
        self._hover_timer.timeout.connect(self._show_detail_dialog)
        self._hover_row = -1
        self._detail_dialog = None

        layout.addWidget(self._table)
        return tab

    @staticmethod
    def _fmt_count(v) -> str:
        """수치 문자열을 천단위 콤마로 정리('3632'→'3,632'). 만/천 표기는 유지."""
        s = str(v or "").strip()
        if not s:
            return ""
        raw = s.replace(",", "")
        if raw.isdigit():
            return f"{int(raw):,}"
        return s

    def _build_log_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        self._log_text = QTextEdit()
        self._log_text.setReadOnly(True)
        layout.addWidget(self._log_text)

        # 로그인 배너 — waiting_login_signal 시 표시, 기본 숨김
        self._login_banner = QFrame()
        self._login_banner.setObjectName("loginBanner")
        self._login_banner.setStyleSheet(
            "QFrame#loginBanner { background: #2a1f00; border: 1px solid #f5a623; border-radius: 6px; }"
        )
        banner_layout = QHBoxLayout(self._login_banner)
        banner_layout.setContentsMargins(12, 8, 12, 8)
        self._login_msg_label = QLabel("브라우저에서 Instagram에 로그인 후 아래 버튼을 눌러주세요.")
        self._login_msg_label.setStyleSheet("color: #f5a623; font-weight: bold;")
        self._login_msg_label.setWordWrap(True)
        banner_layout.addWidget(self._login_msg_label, 1)
        btn_login_done = QPushButton("로그인 완료")
        btn_login_done.setObjectName("btnPrimary")
        btn_login_done.setMinimumWidth(100)
        btn_login_done.clicked.connect(self.login_done_requested)
        banner_layout.addWidget(btn_login_done)
        self._login_banner.setVisible(False)
        layout.addWidget(self._login_banner)

        return tab

    # ── Public API ────────────────────────────────────────────────────────────

    @staticmethod
    def log_color(msg: str) -> str:
        """메시지 prefix → 로그 색상(`Colors.*`). 순수 함수(테스트 용이).

        규칙(src/CLAUDE.md §4): [OK]→green, [ERROR]/[에러]/[오류]→red,
        [wait]→amber, [step]→accent_light, [blocked]/[차단]→red,
        [skip]→amber, 그 외→muted2.
        """
        if msg.startswith("[OK]"):
            return C.green
        if any(x in msg for x in ("[ERROR]", "[에러]", "[오류]")):
            return C.red
        if msg.startswith("[blocked]") or msg.startswith("[차단]"):
            return C.red
        if msg.startswith("[wait]"):
            return C.amber
        if msg.startswith("[skip]"):
            return C.amber
        if msg.startswith("[step]"):
            return C.accent_light
        return C.muted2

    def append_log(self, msg: str):
        color = self.log_color(msg)
        safe = msg.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        self._log_text.append(f'<span style="color:{color}">{safe}</span>')

    def update_progress(self, current: int, total: int):
        self._progress_bar.setMaximum(total)
        self._progress_bar.setValue(current)

    def set_status(self, text: str):
        self._step_label.setText(text)

    def set_step(self, step: str):
        """현재 step 설명 갱신 + 진행 라벨 반영 (§8)."""
        self._cur_step = step or ""
        self._update_progress_label()

    def set_skip_count(self, count: int):
        """중복 skip 카운터 갱신 + 진행 라벨 반영 (§6/§8)."""
        self._skip_count = int(count)
        self._update_progress_label()

    def collected_count(self) -> int:
        return len(self._results)

    def _update_progress_label(self):
        parts = []
        if self._cur_step:
            parts.append(self._cur_step)
        parts.append(f"수집 {len(self._results)}")
        parts.append(f"중복skip {self._skip_count}")
        self._progress_label.setText(" · ".join(parts))

    def add_result(self, info: dict):
        self._results.append(info)
        self._add_table_row(info)
        self._count_label.setText(f"{len(self._results)} collected")
        self._update_progress_label()

    def _add_table_row(self, info: dict):
        from PyQt6.QtGui import QColor, QFont
        row = self._table.rowCount()
        self._table.insertRow(row)

        # # (회색, 가운데)
        num = QTableWidgetItem(str(row + 1))
        num.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        num.setForeground(QColor(C.muted2))
        self._table.setItem(row, 0, num)

        # 유저네임 (보라 강조, 굵게)
        username = info.get("username") or info.get("account", "").lstrip("@")
        user_item = QTableWidgetItem("@" + username if username else "")
        user_item.setForeground(QColor(C.accent_light))
        f = QFont(); f.setBold(True); user_item.setFont(f)
        user_item.setData(Qt.ItemDataRole.UserRole, info.get("profile_url", ""))
        user_item.setToolTip("더블클릭 → 프로필 열기")
        self._table.setItem(row, 1, user_item)

        # 팔로워 / 팔로잉 / 게시물 (우측정렬, 천단위)
        for col, key in ((2, "followers"), (3, "following"), (4, "posts_count")):
            it = QTableWidgetItem(self._fmt_count(info.get(key, "")))
            it.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            if col == 2:
                it.setForeground(QColor(C.text))
            self._table.setItem(row, col, it)

        # 소개 (한 줄, 잘림 + 툴팁 전체)
        bio = (info.get("bio", "") or "").replace("\n", " ").strip()
        bio_item = QTableWidgetItem(bio[:120])
        if bio:
            bio_item.setToolTip(bio)
            bio_item.setForeground(QColor(C.muted2))
        self._table.setItem(row, 5, bio_item)

        # 링크 (웹사이트>게시물>프로필 순으로 열기)
        target = info.get("website") or info.get("post_url") or info.get("profile_url", "")
        link_item = QTableWidgetItem("열기" if target else "")
        link_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        if target:
            link_item.setForeground(QColor(C.accent))
            link_item.setData(Qt.ItemDataRole.UserRole, target)
            link_item.setToolTip(target)
        self._table.setItem(row, 6, link_item)

    def load_existing(self):
        """기존 results.csv 를 표에 불러와 누적분이 항상 보이게 한다."""
        try:
            rows = storage.load_results()
        except Exception:
            rows = []
        self._results = []
        self._table.setRowCount(0)
        for info in rows:
            self._results.append(info)
            self._add_table_row(info)
        self._count_label.setText(f"{len(self._results)} collected")

    def reset(self):
        # 로그/진행만 초기화하고, 결과 표는 누적분(csv)을 다시 보여준다
        # (새 수집을 시작해도 이전 결과가 사라지지 않도록).
        self._log_text.clear()
        self._progress_bar.setValue(0)
        self._step_label.setText("Waiting to start")
        self._cur_step = ""
        self._skip_count = 0
        self.load_existing()          # self._results 를 csv 누적분으로 갱신
        self._update_progress_label()  # 그 후 라벨 갱신(누적 수 반영)

    def show_log_tab(self):
        self._tabs.setCurrentIndex(1)

    def show_results_tab(self):
        self._tabs.setCurrentIndex(0)

    def show_login_banner(self, msg: str = ""):
        """로그인 대기 배너 표시 (로그 탭 전환 포함)."""
        if msg:
            self._login_msg_label.setText(msg)
        self._login_banner.setVisible(True)
        self.show_log_tab()

    def hide_login_banner(self):
        """로그인 완료 후 배너 숨김."""
        self._login_banner.setVisible(False)

    # ── Cell interactions ─────────────────────────────────────────────────────

    def _on_cell_hovered(self, row: int, col: int):
        if row == self._hover_row:
            return
        self._hover_row = row
        self._hover_timer.stop()
        if self._detail_dialog is not None:
            self._detail_dialog.close()
            self._detail_dialog = None
        self._hover_timer.start()

    def _show_detail_dialog(self):
        row = self._hover_row
        if row < 0 or row >= len(self._results):
            return
        from ui.dialogs.profile_detail_dialog import ProfileDetailDialog
        info = self._results[row]
        dlg = ProfileDetailDialog(info, self)
        pos = QCursor.pos()
        dlg.move(pos.x() + 16, pos.y() + 8)
        dlg.show()
        self._detail_dialog = dlg

    def _on_cell_double_clicked(self, row: int, col: int):
        # 유저네임(1) → 프로필, 링크(6) → 웹사이트/게시물. 그 외엔 무시.
        item = self._table.item(row, col)
        if item is None or col not in (1, 6):
            return
        url = item.data(Qt.ItemDataRole.UserRole)
        if url:
            QDesktopServices.openUrl(QUrl(url))

    # ── Import / Export ───────────────────────────────────────────────────────

    def _import_csv(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Import CSV", "", "CSV Files (*.csv)"
        )
        if not path:
            return
        try:
            import csv
            loaded = []
            with open(path, newline="", encoding="utf-8-sig") as f:
                for row in csv.DictReader(f):
                    loaded.append(dict(row))
            if not loaded:
                QMessageBox.information(self, "Info", "No data found in file.")
                return
            for info in loaded:
                self._results.append(info)
                self._add_table_row(info)
            self._count_label.setText(f"{len(self._results)} collected")
            QMessageBox.information(self, "Done", f"Imported {len(loaded)} rows.")
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))

    def _export_csv(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export CSV", "results.csv", "CSV Files (*.csv)"
        )
        if not path:
            return
        try:
            # Try to copy the live results.csv first (fastest, preserves all fields)
            storage.export_results(path)
            QMessageBox.information(self, "Done", f"Saved: {path}")
            return
        except FileNotFoundError:
            pass
        # Fallback: write from in-memory results
        if not self._results:
            QMessageBox.information(self, "Info", "No results to export.")
            return
        import csv
        fieldnames = list(self._results[0].keys())
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(self._results)
        QMessageBox.information(self, "Done", f"Saved: {path}")
