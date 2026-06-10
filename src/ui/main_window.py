from PyQt6.QtCore import Qt, QEvent
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QMainWindow, QSplitter, QStackedWidget, QWidget, QVBoxLayout,
    QSystemTrayIcon, QMenu, QMessageBox, QApplication, QLabel,
)

import core.storage as storage
from core.run_logger import RunLogger
from ui.panels.control_panel import ControlPanel
from ui.panels.results_panel import ResultsPanel
from ui.settings_view import SettingsView

try:
    from ui.panels.browser_panel import BrowserPanel
    _HAS_WEBENGINE = True
except Exception:
    _HAS_WEBENGINE = False


class MainWindow(QMainWindow):
    def __init__(self, icon: QIcon | None = None):
        super().__init__()
        self.setWindowTitle("인플루언서 시딩기")
        self.setMinimumSize(1280, 760)
        self.resize(1480, 900)
        if icon and not icon.isNull():
            self.setWindowIcon(icon)

        # 보조 창(호버 상세 다이얼로그·QMessageBox·파일 다이얼로그 등)이 닫힐 때
        # Qt 가 '마지막 창이 닫혔다'고 보고 앱을 자동 종료하는 것을 막는다.
        # 종료는 오직 메인 창 X / 트레이 '종료' → closeEvent → quit() 로만 일어난다.
        app = QApplication.instance()
        if app is not None:
            app.setQuitOnLastWindowClosed(False)

        self._scraper = None  # EmbeddedScraper (or None)
        self._scrape_had_error = False
        self._run_logger: RunLogger | None = None
        self._tray: QSystemTrayIcon | None = None
        self._skip_count = 0
        self._browser = None  # BrowserPanel (WebEngine이 있을 때만)
        self._build_ui()
        self._setup_tray()
        # 시작 시 기존 누적 결과(results.csv)를 표에 표시.
        try:
            self._results.load_existing()
        except Exception:
            pass

    def _build_ui(self):
        self._stack = QStackedWidget()
        self.setCentralWidget(self._stack)

        # Page 0: main view — 3-패널 (컨트롤 | 브라우저 | 결과/로그)
        outer = QSplitter(Qt.Orientation.Horizontal)
        outer.setHandleWidth(1)

        self._control = ControlPanel()
        self._control.start_requested.connect(self._start_scrape)
        self._control.resume_requested.connect(self._resume_scrape)
        self._control.stop_requested.connect(self._stop_scrape)
        self._control.reset_requested.connect(self._reset)
        self._control.settings_requested.connect(self.show_settings)
        outer.addWidget(self._control)

        # 중간: 임베디드 브라우저 (WebEngine 사용 가능 시)
        # 뷰는 iPhone 크기(390x844)로 고정 — 남는 공간 안에서 가운데 정렬한다.
        if _HAS_WEBENGINE:
            self._browser = BrowserPanel()
            browser_wrap = QWidget()
            wrap_l = QVBoxLayout(browser_wrap)
            wrap_l.setContentsMargins(0, 0, 0, 0)
            wrap_l.addStretch()
            wrap_l.addWidget(self._browser, alignment=Qt.AlignmentFlag.AlignHCenter)
            wrap_l.addStretch()
            outer.addWidget(browser_wrap)
        else:
            placeholder = QLabel(
                "임베디드 브라우저(QtWebEngine) 미지원\n\n"
                "PyQt6-WebEngine 설치 후 재시작:\n"
                "pip install PyQt6-WebEngine"
            )
            placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            placeholder.setObjectName("labelMuted")
            outer.addWidget(placeholder)

        self._results = ResultsPanel()
        self._results.login_done_requested.connect(self._login_done)
        outer.addWidget(self._results)

        # 임베디드 브라우저는 고정 폭(≈293)이라 가운데 패널은 좁게,
        # 남는 폭은 결과 패널에 더 준다: 컨트롤 | 브라우저 | 결과(넓게).
        outer.setSizes([300, 320, 760])
        outer.setStretchFactor(0, 0)
        outer.setStretchFactor(1, 0)
        outer.setStretchFactor(2, 1)   # 창을 키우면 결과 패널이 늘어남
        self._stack.addWidget(outer)

        # Page 1: settings view
        self._settings_view = SettingsView()
        self._settings_view.back_requested.connect(self.show_main)
        self._stack.addWidget(self._settings_view)

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def show_main(self):
        # 설정에서 편집한 타겟(검색 조건)·제외 계정을 컨트롤 패널에 즉시 반영.
        self._stack.setCurrentIndex(0)
        self._control.apply_target(storage.load_target())
        self._control.reload_excluded()
        self._refresh_resume()

    def _refresh_resume(self):
        """[이어하기] 활성 조건은 state.json 존재 (§7)."""
        self._control.set_resume_available(storage.load_state() is not None)

    def show_settings(self):
        # 컨트롤 패널의 현재 검색 조건을 target.csv 에 먼저 반영(양방향 동기화) —
        # 타겟 전용 필드는 보존하고 공유 필드만 덮어쓴다.
        merged = {**storage.load_target(), **self._control.current_target()}
        storage.save_target(merged)
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
        """[이어하기] — state.json 의 진행 상태를 스크래퍼에 주입 (§7)."""
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
        """EmbeddedScraper 생성자에 넘길 config 를 구성. flow/target/selectors 는
        storage 에서 로드해 주입한다(생성자도 self-load 하지만 경로 통일)."""
        merged = dict(params)
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
        # 진행률 알림용: 통과한 마일스톤(%) 추적.
        self._notified_milestones: set[int] = set()

        # Persistent run-log file (§8): created per run, closed on done.
        try:
            self._run_logger = RunLogger()
        except Exception:
            self._run_logger = None

        full = self._build_params(params, resume_state)
        # 이미 열린 임베디드 브라우저에서 직접 수집(JS 클릭 방식). WebEngine 이
        # 없으면 임베디드 브라우저가 없어 수집 불가 → 안내 후 중단.
        if self._browser is None:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(
                self, "수집 불가",
                "임베디드 브라우저(QtWebEngine)를 사용할 수 없습니다.\n"
                "PyQt6-WebEngine 설치 후 다시 실행해주세요.",
            )
            self._control.set_running(False)
            return
        from core.embedded_scraper import EmbeddedScraper
        self._scraper = EmbeddedScraper(self._browser, **full)
        self._scraper.log_signal.connect(self._results.append_log)
        self._scraper.log_signal.connect(self._log_to_file)
        self._scraper.step_signal.connect(self._on_step)
        self._scraper.progress_signal.connect(self._results.update_progress)
        self._scraper.progress_signal.connect(self._on_progress)
        self._scraper.result_signal.connect(self._results.add_result)
        self._scraper.skip_signal.connect(self._on_skip)
        self._scraper.blocked_signal.connect(self._on_blocked)
        self._scraper.done_signal.connect(self._on_done)
        self._scraper.error_signal.connect(self._on_error)
        self._scraper.waiting_login_signal.connect(self._on_waiting_login)
        self._scraper.login_ok_signal.connect(self._on_login_ok)
        self._scraper.start()

    def _on_login_ok(self):
        """로그인/홈 자동 확인됨 → 안내 배너 닫고 수집 상태로."""
        self._results.hide_login_banner()
        self._control.set_running(True, waiting_login=False)
        self._results.set_status("수집 중...")

    def _login_done(self):
        if self._scraper:
            self._scraper.login_done()
        self._results.hide_login_banner()
        self._control.set_running(True, waiting_login=False)
        self._results.set_status("수집 중...")

    def _stop_scrape(self):
        """정지 버튼 → 스크래퍼 중단, UI 복원."""
        if self._scraper and self._scraper.isRunning():
            self._scraper.stop()
        self._control.set_running(False)
        self._results.set_status("수집 중단됨")

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

    def _on_progress(self, done: int, total: int):
        """progress_signal → 25/50/75% 마일스톤마다 트레이 알림(중복 없이 1회씩)."""
        if total <= 0:
            return
        pct = int(done * 100 / total)
        for m in (25, 50, 75):
            if pct >= m and m not in self._notified_milestones:
                self._notified_milestones.add(m)
                self._notify_tray(
                    "수집 진행 중", f"{m}% 완료 — {done}/{total}명 수집"
                )

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
        self._results.show_login_banner(
            "Chrome 브라우저에서 Instagram에 로그인 후 [로그인 완료] 버튼을 눌러주세요."
        )

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
        self.close()

    def _notify_tray(self, title: str, message: str):
        """트레이 알림. 창이 숨겨졌거나 최소화됐을 때(=보고 있지 않을 때) 팝업."""
        if self._tray is not None:
            try:
                self._tray.setToolTip(f"{title} · {message}")
                if not self.isVisible() or self.isMinimized():
                    self._tray.showMessage(title, message)
            except Exception:
                pass

    def changeEvent(self, event):
        """최소화해도 창을 숨기지(hide) 않고 그냥 최소화 상태로 둔다.

        창을 hide() 하면 QtWebEngine 렌더 위젯이 unmap 되어 페이지가
        멈추거나 실제 클릭이 안 먹을 수 있다. 최소화(mapped) 상태로 두면
        backgrounding 방지 플래그(main.py)와 함께 웹뷰가 살아서 수집이 계속된다.
        최초 최소화 때 한 번만 안내 알림."""
        if (
            event.type() == QEvent.Type.WindowStateChange
            and self.isMinimized()
            and not getattr(self, "_min_notified", False)
        ):
            self._min_notified = True
            self._notify_tray("최소화됨", "최소화 상태에서도 수집은 계속됩니다")
        super().changeEvent(event)

    def closeEvent(self, event):
        """닫기(X) → 완전 종료. 백그라운드 실행은 최소화(−) 버튼으로만."""
        if self._scraper and self._scraper.isRunning():
            self._scraper.stop()
            self._scraper.wait(2000)
        if self._run_logger is not None:
            self._run_logger.close()
            self._run_logger = None
        if self._tray is not None:
            self._tray.hide()
        event.accept()
        # QLocalServer/QSystemTrayIcon 등이 이벤트 루프를 살려두는 것을 명시 종료
        QApplication.instance().quit()
