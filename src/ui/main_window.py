from PyQt6.QtCore import Qt, QEvent
from PyQt6.QtWidgets import (
    QMainWindow, QSplitter, QStackedWidget,
    QSystemTrayIcon, QMenu, QMessageBox, QApplication,
)

import core.storage as storage
from core.scraper import ScraperThread
from core.run_logger import RunLogger
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
        self._run_logger: RunLogger | None = None
        self._tray: QSystemTrayIcon | None = None
        self._skip_count = 0
        self._build_ui()
        self._setup_tray()

    def _build_ui(self):
        self._stack = QStackedWidget()
        self.setCentralWidget(self._stack)

        # Page 0: main view
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)
        self._control = ControlPanel()
        self._results = ResultsPanel()
        self._control.start_requested.connect(self._start_scrape)
        self._control.resume_requested.connect(self._resume_scrape)
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
        self._refresh_resume()

    def _refresh_resume(self):
        """[이어하기] 활성 조건은 state.json 존재 (§7)."""
        self._control.set_resume_available(storage.load_state() is not None)

    def show_settings(self):
        self._settings_view.load()
        self._stack.setCurrentIndex(1)

    # ------------------------------------------------------------------
    # Scraper control
    # ------------------------------------------------------------------

    def _start_scrape(self, params: dict):
        """신규 스크랩 — 이어하기 아니므로 기존 진행 상태를 비운다 (§7)."""
        try:
            storage.clear_state()
        except Exception:
            pass
        self._launch_scrape(params, resume_state=None)

    def _resume_scrape(self):
        """[이어하기] — state.json 의 진행 상태를 ScraperThread 에 주입 (§7)."""
        state = storage.load_state()
        if state is None:
            return
        params = self._control.collect_params()
        if params is None:
            return
        kw = state.get("keyword")
        if kw:
            params["search_term"] = kw
        self._launch_scrape(params, resume_state=state)

    def _build_params(self, params: dict, resume_state: dict | None) -> dict:
        """ScraperThread 생성자 시그니처(Push2)에 맞춰 config 그룹을 주입한다.

        web/delays/flow/target 은 storage 에서 로드해 주입(생성자가 self-load 도
        하지만, 명시 주입으로 [이어하기]/신규 경로를 통일). resume 이면 resume_state
        를 넣는다.
        """
        merged = dict(params)
        merged.setdefault("web", storage.load_web())
        merged.setdefault("delays", storage.load_delays())
        merged.setdefault("flow", storage.load_flow())
        merged.setdefault("target", storage.load_target())
        merged["resume_state"] = resume_state
        return merged

    def _launch_scrape(self, params: dict, resume_state: dict | None):
        if self._scraper and self._scraper.isRunning():
            return

        self._results.reset()
        self._results.update_progress(0, params["count"])
        self._results.set_status("수집 중...")
        self._control.set_running(True)
        self._scrape_had_error = False
        self._skip_count = 0

        # Persistent run-log file (§8): created per run, closed on done.
        try:
            self._run_logger = RunLogger()
        except Exception:
            self._run_logger = None

        full = self._build_params(params, resume_state)
        self._scraper = ScraperThread(**full)
        self._scraper.log_signal.connect(self._results.append_log)
        self._scraper.log_signal.connect(self._log_to_file)
        self._scraper.step_signal.connect(self._on_step)
        self._scraper.progress_signal.connect(self._results.update_progress)
        self._scraper.result_signal.connect(self._results.add_result)
        self._scraper.skip_signal.connect(self._on_skip)
        self._scraper.blocked_signal.connect(self._on_blocked)
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

    def _log_to_file(self, msg: str):
        """log_signal → 영속 로그 파일(§8). prefix 로 LEVEL/step_id 유추."""
        if self._run_logger is None:
            return
        level = "INFO"
        if any(x in msg for x in ("[ERROR]", "[에러]", "[오류]")):
            level = "ERROR"
        elif "[blocked]" in msg or "[차단]" in msg:
            level = "WARNING"
        elif msg.startswith("[wait]"):
            level = "WARNING"
        elif msg.startswith("[step]"):
            level = "STEP"
        self._run_logger.write(level, "-", msg)

    def _on_step(self, step: str):
        """step_signal → 상태 라벨/진행표시 + 영속 로그."""
        self._results.set_step(step)
        if self._run_logger is not None:
            self._run_logger.write("STEP", step, step)

    def _on_skip(self, username: str):
        """skip_signal → 중복 skip 카운터 누적 + 진행 라벨 갱신 (§6)."""
        self._skip_count += 1
        self._results.set_skip_count(self._skip_count)
        if self._run_logger is not None:
            self._run_logger.write("INFO", "skip", f"중복 건너뜀: @{username}")

    def _on_blocked(self):
        """blocked_signal → 모달 경고 + 스크래퍼 일시정지/중단 (§5)."""
        if self._run_logger is not None:
            self._run_logger.write("WARNING", "blocked", "차단/챌린지 감지 - 일시정지")
        self._results.append_log("[blocked] 차단 감지 - 수집을 중단합니다")
        if self._scraper:
            self._scraper.stop()
        QMessageBox.warning(
            self,
            "차단 감지",
            "인스타그램이 봇 활동을 감지해 로그인/챌린지 화면으로 전환되었습니다.\n"
            "수집을 일시중단했습니다. 잠시 후 다시 시도하거나 직접 로그인 상태를 확인하세요.",
        )

    def _on_error(self, msg: str):
        self._scrape_had_error = True
        self._results.append_log(f"[에러] {msg}")

    def _on_done(self):
        self._control.set_running(False)
        if self._run_logger is not None:
            self._run_logger.write(
                "INFO", "done",
                f"수집 종료 (수집 {self._results.collected_count()} · 중복skip {self._skip_count})",
            )
            self._run_logger.close()
            self._run_logger = None
        if self._scrape_had_error:
            self._results.set_status("오류 발생 - 로그 확인")
            self._results.show_log_tab()
            self._notify_tray("수집 중단", "오류가 발생했습니다 - 로그를 확인하세요")
        else:
            self._results.set_status("완료!")
            self._results.show_results_tab()
            self._notify_tray("수집 완료", f"{self._results.collected_count()}명 수집 완료")
        self._refresh_resume()

    def _on_waiting_login(self):
        self._control.set_running(True, waiting_login=True)
        self._results.set_status("브라우저에서 로그인 후 버튼을 눌러주세요")
        self._results.show_log_tab()

        self._login_dialog = LoginWaitDialog(self)
        self._login_dialog.accepted.connect(self._login_done)
        self._login_dialog.show()

    def reload_excluded(self, accounts: list[str]):
        self._control.excluded_widget.reload(accounts)

    # ------------------------------------------------------------------
    # System tray (§4) — background minimize
    # ------------------------------------------------------------------

    def _setup_tray(self):
        """트레이 아이콘 + 컨텍스트 메뉴. 미지원 환경에서는 조용히 비활성(§4)."""
        try:
            if not QSystemTrayIcon.isSystemTrayAvailable():
                self._tray = None
                return
            tray = QSystemTrayIcon(self)
            icon = self.windowIcon()
            if icon.isNull():
                style = QApplication.instance().style()
                from PyQt6.QtWidgets import QStyle
                icon = style.standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)
            tray.setIcon(icon)
            tray.setToolTip("인플루언서 시딩기")

            menu = QMenu()
            act_show = menu.addAction("열기")
            act_show.triggered.connect(self._restore_from_tray)
            act_quit = menu.addAction("종료")
            act_quit.triggered.connect(self._quit_from_tray)
            tray.setContextMenu(menu)
            tray.activated.connect(self._on_tray_activated)
            tray.show()
            self._tray = tray
        except Exception:
            self._tray = None

    def _on_tray_activated(self, reason):
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self._restore_from_tray()

    def _restore_from_tray(self):
        """트레이에서 복귀: 최소화 상태를 해제하고 숨기기 직전의 geometry 를 복원해
        실행 중 화면을 원래 크기/위치로 다시 보여준다(§4)."""
        self.setWindowState(self.windowState() & ~Qt.WindowState.WindowMinimized)
        geo = getattr(self, "_saved_geometry", None)
        if geo is not None:
            self.restoreGeometry(geo)
        self.showNormal()
        self.show()
        self.raise_()
        self.activateWindow()

    def _quit_from_tray(self):
        self._force_quit = True
        self.close()

    def _notify_tray(self, title: str, message: str):
        """트레이 알림(미지원/숨김 아닐 때만)."""
        if self._tray is not None:
            try:
                self._tray.setToolTip(f"{title} · {message}")
                if not self.isVisible():
                    self._tray.showMessage(title, message)
            except Exception:
                pass

    def changeEvent(self, event):
        """최소화 시 트레이로 숨긴다(트레이 사용 가능 시). 수집은 QThread 라 계속."""
        if (
            event.type() == QEvent.Type.WindowStateChange
            and self.isMinimized()
            and self._tray is not None
        ):
            event.accept()
            # 숨기기 직전 geometry 저장 → 복귀 시 원래 크기/위치 복원(§4).
            self._saved_geometry = self.saveGeometry()
            # defer hide so the state change settles
            self.hide()
            self._notify_tray("백그라운드 실행 중", "트레이에서 계속 수집합니다")
            return
        super().changeEvent(event)

    def closeEvent(self, event):
        # 트레이 사용 가능 + 강제종료 아님 → 닫기 대신 트레이로 숨김(§4).
        if self._tray is not None and not getattr(self, "_force_quit", False):
            event.ignore()
            # 숨기기 직전 geometry 저장 → 복귀 시 원래 크기/위치 복원(§4).
            self._saved_geometry = self.saveGeometry()
            self.hide()
            self._notify_tray("백그라운드 실행 중", "트레이에서 계속 수집합니다")
            return
        if self._scraper and self._scraper.isRunning():
            self._scraper.stop()
            self._scraper.wait(3000)
        if self._run_logger is not None:
            self._run_logger.close()
            self._run_logger = None
        if self._tray is not None:
            self._tray.hide()
        event.accept()
