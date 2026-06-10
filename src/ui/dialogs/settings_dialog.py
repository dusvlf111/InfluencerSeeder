import sys
from pathlib import Path

from PyQt6.QtCore import QProcess
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QGridLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTextEdit,
    QTabWidget, QWidget, QFileDialog, QMessageBox,
)

import core.storage as storage
import core.sheets as sheets_api

_EYE_OPEN  = "show"
_EYE_CLOSE = "hide"


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("설정")
        self.setMinimumWidth(540)
        self._settings = storage.load_settings()
        self._process: QProcess | None = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        tabs = QTabWidget()

        tabs.addTab(self._build_instagram_tab(), "인스타그램 계정")
        tabs.addTab(self._build_selectors_tab(), "셀렉터")
        tabs.addTab(self._build_sheets_tab(), "구글 시트")
        tabs.addTab(self._build_deps_tab(), "의존성 설치")

        layout.addWidget(tabs)

        btn_save = QPushButton("저장")
        btn_save.setObjectName("btnPrimary")
        btn_save.clicked.connect(self._save)
        layout.addWidget(btn_save)

    # ── 인스타그램 계정 탭 ──────────────────────────────────────────────────────

    def _build_instagram_tab(self) -> QWidget:
        tab = QWidget()
        grid = QGridLayout(tab)
        grid.setSpacing(10)

        # 안내 문구
        note = QLabel(
            "저장 시 로그인 ID·비밀번호가 로컬 JSON 파일에 평문으로 저장됩니다.\n"
            "입력 시 수집 시작 시 자동 로그인을 시도합니다."
        )
        note.setObjectName("labelMuted")
        note.setWordWrap(True)
        grid.addWidget(note, 0, 0, 1, 2)

        # 아이디
        grid.addWidget(QLabel("아이디"), 1, 0)
        self._ig_username = QLineEdit(self._settings.get("instagram_username", ""))
        self._ig_username.setPlaceholderText("Instagram 아이디")
        grid.addWidget(self._ig_username, 1, 1)

        # 비밀번호 (마스킹 + 보기 토글)
        grid.addWidget(QLabel("비밀번호"), 2, 0)
        pw_row = QWidget()
        pw_layout = QHBoxLayout(pw_row)
        pw_layout.setContentsMargins(0, 0, 0, 0)
        self._ig_password = QLineEdit(self._settings.get("instagram_password", ""))
        self._ig_password.setPlaceholderText("Instagram 비밀번호")
        self._ig_password.setEchoMode(QLineEdit.EchoMode.Password)
        self._btn_toggle_pw = QPushButton(_EYE_OPEN)
        self._btn_toggle_pw.setFixedWidth(36)
        self._btn_toggle_pw.setCheckable(True)
        self._btn_toggle_pw.clicked.connect(self._toggle_password_visibility)
        pw_layout.addWidget(self._ig_password)
        pw_layout.addWidget(self._btn_toggle_pw)
        grid.addWidget(pw_row, 2, 1)

        # 초기화 버튼
        btn_clear = QPushButton("저장된 계정 정보 삭제")
        btn_clear.clicked.connect(self._clear_instagram_creds)
        grid.addWidget(btn_clear, 3, 0, 1, 2)

        grid.setRowStretch(4, 1)
        return tab

    def _toggle_password_visibility(self, checked: bool):
        if checked:
            self._ig_password.setEchoMode(QLineEdit.EchoMode.Normal)
            self._btn_toggle_pw.setText(_EYE_CLOSE)
        else:
            self._ig_password.setEchoMode(QLineEdit.EchoMode.Password)
            self._btn_toggle_pw.setText(_EYE_OPEN)

    def _clear_instagram_creds(self):
        self._ig_username.clear()
        self._ig_password.clear()

    # -- Selectors tab -------------------------------------------------------

    def _build_selectors_tab(self) -> QWidget:
        from PyQt6.QtWidgets import QScrollArea, QFormLayout
        from PyQt6.QtCore import Qt

        container = QWidget()
        form = QFormLayout(container)
        form.setSpacing(8)
        form.setContentsMargins(12, 12, 12, 12)

        def note(text: str) -> QLabel:
            lbl = QLabel(text)
            lbl.setObjectName("labelMuted")
            lbl.setWordWrap(True)
            return lbl

        form.addRow(note(
            "Instagram DOM selectors. Edit only when Instagram's UI changes "
            "and scraping breaks. Use comma-separated values for label lists."
        ))

        # Login form selectors
        form.addRow(QLabel("--- Login form ---"))

        self._sel_login_user = QLineEdit(self._settings.get("sel_login_user_field", "username"))
        form.addRow("Username field (name=)", self._sel_login_user)

        self._sel_login_pass = QLineEdit(self._settings.get("sel_login_pass_field", "password"))
        form.addRow("Password field (name=)", self._sel_login_pass)

        self._sel_login_btn = QLineEdit(self._settings.get("sel_login_btn_xpath", "//button[@type='submit']"))
        form.addRow("Login button (XPath)", self._sel_login_btn)

        # Post-login popup
        form.addRow(QLabel("--- Post-login popup ---"))

        self._sel_dismiss = QLineEdit(self._settings.get("sel_dismiss_popup", ""))
        self._sel_dismiss.setPlaceholderText("label1,label2,...")
        form.addRow("Dismiss popup labels", self._sel_dismiss)

        # Tab navigation
        form.addRow(QLabel("--- Tab labels (comma-separated) ---"))

        self._sel_tab_recent = QLineEdit(self._settings.get("sel_tab_recent", ""))
        self._sel_tab_recent.setPlaceholderText("최근,Recent")
        form.addRow("Recent tab", self._sel_tab_recent)

        self._sel_tab_posts = QLineEdit(self._settings.get("sel_tab_posts", ""))
        self._sel_tab_posts.setPlaceholderText("게시물,Posts")
        form.addRow("Posts tab", self._sel_tab_posts)

        self._sel_tab_tags = QLineEdit(self._settings.get("sel_tab_tags", ""))
        self._sel_tab_tags.setPlaceholderText("태그,Tags,해시태그")
        form.addRow("Tags tab", self._sel_tab_tags)

        # Username CSS selectors
        form.addRow(QLabel("--- Username extraction CSS (one per line) ---"))

        self._sel_username_css = QTextEdit()
        self._sel_username_css.setPlainText(self._settings.get("sel_username_css", ""))
        self._sel_username_css.setFixedHeight(80)
        form.addRow("CSS selectors", self._sel_username_css)

        # Post link xpath
        form.addRow(QLabel("--- Post link collection ---"))

        self._sel_post_links = QLineEdit(self._settings.get("sel_post_links_xpath", ""))
        self._sel_post_links.setPlaceholderText("//a[contains(@href, '/p/')]")
        form.addRow("Post links (XPath)", self._sel_post_links)

        # Reset button
        btn_reset = QPushButton("Reset to defaults")
        btn_reset.clicked.connect(self._reset_selectors)
        form.addRow(btn_reset)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(container)

        outer = QWidget()
        outer_layout = QVBoxLayout(outer)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.addWidget(scroll)
        return outer

    def _reset_selectors(self):
        from core.storage import selector_defaults
        d = selector_defaults()
        self._sel_login_user.setText(d["sel_login_user_field"])
        self._sel_login_pass.setText(d["sel_login_pass_field"])
        self._sel_login_btn.setText(d["sel_login_btn_xpath"])
        self._sel_dismiss.setText(d["sel_dismiss_popup"])
        self._sel_tab_recent.setText(d["sel_tab_recent"])
        self._sel_tab_posts.setText(d["sel_tab_posts"])
        self._sel_tab_tags.setText(d["sel_tab_tags"])
        self._sel_username_css.setPlainText(d["sel_username_css"])
        self._sel_post_links.setText(d["sel_post_links_xpath"])

    # ── 구글 시트 탭 ────────────────────────────────────────────────────────────

    def _build_sheets_tab(self) -> QWidget:
        tab = QWidget()
        grid = QGridLayout(tab)
        grid.setSpacing(10)

        grid.addWidget(QLabel("Spreadsheet ID"), 0, 0)
        self._sheets_id = QLineEdit(self._settings.get("sheets_spreadsheet_id", ""))
        self._sheets_id.setPlaceholderText("URL 내 /d/…/edit 사이의 ID")
        grid.addWidget(self._sheets_id, 0, 1)

        grid.addWidget(QLabel("서비스 계정 JSON"), 1, 0)
        cred_row = QWidget()
        cred_layout = QHBoxLayout(cred_row)
        cred_layout.setContentsMargins(0, 0, 0, 0)
        self._cred_path = QLineEdit(self._settings.get("sheets_credential_path", ""))
        self._cred_path.setPlaceholderText("JSON 파일 경로")
        btn_browse = QPushButton("찾기...")
        btn_browse.setFixedWidth(72)
        btn_browse.clicked.connect(self._browse_credential)
        cred_layout.addWidget(self._cred_path)
        cred_layout.addWidget(btn_browse)
        grid.addWidget(cred_row, 1, 1)

        btn_row = QWidget()
        btn_layout = QHBoxLayout(btn_row)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_test = QPushButton("연결 테스트")
        btn_test.clicked.connect(self._test_connection)
        btn_load = QPushButton("제외계정 불러오기")
        btn_load.clicked.connect(self._load_excluded)
        btn_layout.addWidget(btn_test)
        btn_layout.addWidget(btn_load)
        btn_layout.addStretch()
        grid.addWidget(btn_row, 2, 0, 1, 2)

        self._sheets_log = QTextEdit()
        self._sheets_log.setReadOnly(True)
        self._sheets_log.setMaximumHeight(80)
        grid.addWidget(self._sheets_log, 3, 0, 1, 2)

        return tab

    def _browse_credential(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "서비스 계정 JSON 선택", "", "JSON Files (*.json)"
        )
        if path:
            self._cred_path.setText(path)

    def _test_connection(self):
        sid, cred = self._sheets_id.text().strip(), self._cred_path.text().strip()
        if not sid or not cred:
            self._sheets_log.setPlainText("ID와 JSON 경로를 모두 입력하세요.")
            return
        try:
            title = sheets_api.test_connection(sid, cred)
            self._sheets_log.setPlainText(f"연결 성공: {title}")
        except Exception as e:
            self._sheets_log.setPlainText(f"연결 실패: {e}")

    def _load_excluded(self):
        sid, cred = self._sheets_id.text().strip(), self._cred_path.text().strip()
        if not sid or not cred:
            self._sheets_log.setPlainText("ID와 JSON 경로를 모두 입력하세요.")
            return
        try:
            accounts = sheets_api.load_excluded_from_sheets(sid, cred)
            existing = storage.load_excluded()
            merged = sorted(set(existing) | set(accounts))
            storage.save_excluded(merged)
            self._sheets_log.setPlainText(
                f"제외계정 {len(accounts)}개 불러와 로컬에 병합 완료."
            )
            if self.parent() and hasattr(self.parent(), "reload_excluded"):
                self.parent().reload_excluded(merged)
        except Exception as e:
            self._sheets_log.setPlainText(f"오류: {e}")

    # ── 의존성 설치 탭 ──────────────────────────────────────────────────────────

    def _build_deps_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.addWidget(QLabel("requirements.txt 기준으로 패키지를 설치합니다."))
        btn_install = QPushButton("pip install 실행")
        btn_install.clicked.connect(self._run_install)
        layout.addWidget(btn_install)
        self._install_log = QTextEdit()
        self._install_log.setReadOnly(True)
        layout.addWidget(self._install_log)
        return tab

    def _run_install(self):
        req = str(Path(__file__).parent.parent.parent / "requirements.txt")
        self._install_log.clear()
        self._process = QProcess(self)
        self._process.readyReadStandardOutput.connect(
            lambda: self._install_log.append(
                self._process.readAllStandardOutput().data().decode(errors="replace")
            )
        )
        self._process.readyReadStandardError.connect(
            lambda: self._install_log.append(
                self._process.readAllStandardError().data().decode(errors="replace")
            )
        )
        self._process.start(sys.executable, ["-m", "pip", "install", "-r", req])

    # ── 저장 ───────────────────────────────────────────────────────────────────

    def _save(self):
        self._settings["instagram_username"] = self._ig_username.text().strip()
        self._settings["instagram_password"] = self._ig_password.text()
        self._settings["sheets_spreadsheet_id"] = self._sheets_id.text().strip()
        self._settings["sheets_credential_path"] = self._cred_path.text().strip()
        self._settings["sel_login_user_field"]  = self._sel_login_user.text().strip()
        self._settings["sel_login_pass_field"]  = self._sel_login_pass.text().strip()
        self._settings["sel_login_btn_xpath"]   = self._sel_login_btn.text().strip()
        self._settings["sel_dismiss_popup"]     = self._sel_dismiss.text().strip()
        self._settings["sel_tab_recent"]        = self._sel_tab_recent.text().strip()
        self._settings["sel_tab_posts"]         = self._sel_tab_posts.text().strip()
        self._settings["sel_tab_tags"]          = self._sel_tab_tags.text().strip()
        self._settings["sel_username_css"]      = self._sel_username_css.toPlainText().strip()
        self._settings["sel_post_links_xpath"]  = self._sel_post_links.text().strip()
        storage.save_settings(self._settings)
        self.accept()
