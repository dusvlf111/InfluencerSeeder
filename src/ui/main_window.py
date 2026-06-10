from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QMainWindow, QSplitter, QStackedWidget

from core.scraper import ScraperThread
from ui.panels.control_panel import ControlPanel
from ui.panels.results_panel import ResultsPanel
from ui.settings_view import SettingsView
from ui.dialogs.login_dialog import LoginWaitDialog


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("인플루언서 시딩기")
        self.setMinimumSize(1100, 700)

        self._scraper: ScraperThread | None = None
        self._scrape_had_error = False
        self._login_dialog: LoginWaitDialog | None = None
        self._build_ui()

    def _build_ui(self):
        self._stack = QStackedWidget()
        self.setCentralWidget(self._stack)

        # Page 0: main view
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)
        self._control = ControlPanel()
        self._results = ResultsPanel()
        self._control.start_requested.connect(self._start_scrape)
        self._control.login_done_requested.connect(self._login_done)
        self._control.reset_requested.connect(self._reset)
        self._control.settings_requested.connect(self.show_settings)
        splitter.addWidget(self._control)
        splitter.addWidget(self._results)
        splitter.setSizes([340, 760])
        self._stack.addWidget(splitter)

        # Page 1: settings view
        self._settings_view = SettingsView()
        self._settings_view.back_requested.connect(self.show_main)
        self._stack.addWidget(self._settings_view)

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def show_main(self):
        self._stack.setCurrentIndex(0)
        self._control._apply_saved_settings()

    def show_settings(self):
        self._settings_view.load()
        self._stack.setCurrentIndex(1)

    # ------------------------------------------------------------------
    # Scraper control
    # ------------------------------------------------------------------

    def _start_scrape(self, params: dict):
        if self._scraper and self._scraper.isRunning():
            return

        self._results.reset()
        self._results.update_progress(0, params["count"])
        self._results.set_status("수집 중...")
        self._control.set_running(True)
        self._scrape_had_error = False

        self._scraper = ScraperThread(**params)
        self._scraper.log_signal.connect(self._results.append_log)
        self._scraper.progress_signal.connect(self._results.update_progress)
        self._scraper.result_signal.connect(self._results.add_result)
        self._scraper.done_signal.connect(self._on_done)
        self._scraper.error_signal.connect(self._on_error)
        self._scraper.waiting_login_signal.connect(self._on_waiting_login)
        self._scraper.start()

    def _login_done(self):
        if self._scraper:
            self._scraper.login_done()
        if self._login_dialog and self._login_dialog.isVisible():
            self._login_dialog.close()
        self._login_dialog = None
        self._control.set_running(True, waiting_login=False)
        self._results.set_status("수집 중...")

    def _reset(self):
        if self._scraper and self._scraper.isRunning():
            self._scraper.stop()
            self._scraper.wait(3000)
        self._results.reset()
        self._control.set_running(False)

    # ------------------------------------------------------------------
    # Signal handlers
    # ------------------------------------------------------------------

    def _on_error(self, msg: str):
        self._scrape_had_error = True
        self._results.append_log(f"[에러] {msg}")

    def _on_done(self):
        self._control.set_running(False)
        if self._scrape_had_error:
            self._results.set_status("오류 발생 - 로그 확인")
            self._results.show_log_tab()
        else:
            self._results.set_status("완료!")
            self._results.show_results_tab()

    def _on_waiting_login(self):
        self._control.set_running(True, waiting_login=True)
        self._results.set_status("브라우저에서 로그인 후 버튼을 눌러주세요")
        self._results.show_log_tab()

        self._login_dialog = LoginWaitDialog(self)
        self._login_dialog.accepted.connect(self._login_done)
        self._login_dialog.show()

    def reload_excluded(self, accounts: list[str]):
        self._control.excluded_widget.reload(accounts)

    def closeEvent(self, event):
        if self._scraper and self._scraper.isRunning():
            self._scraper.stop()
            self._scraper.wait(3000)
        event.accept()
