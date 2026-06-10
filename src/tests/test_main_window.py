"""MainWindow / panels tests (push4 4.2~4.5).

pytest-qt 미설치 — qapp 공유 fixture 로 위젯을 직접 생성하고 메서드를 직접
호출한다(이벤트 루프/실제 클릭 없음). ScraperThread 는 실제 start 하지 않고
patch/MagicMock 으로 생성을 가로채거나 신호를 수동 emit 한다.
"""
import os
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QMessageBox  # noqa: E402

import core.storage as storage  # noqa: E402


@pytest.fixture(autouse=True)
def _tmp_data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "DATA_DIR", tmp_path)
    yield


@pytest.fixture
def window(qapp):
    from ui.main_window import MainWindow
    w = MainWindow()
    yield w
    # avoid trayicon teardown noise; closeEvent 의 종료 확인 모달은 Yes 로 통과
    w._tray = None
    with patch("ui.main_window.QMessageBox.question",
               return_value=QMessageBox.StandardButton.Yes):
        w.close()


# ── 4.2 Tray ────────────────────────────────────────────────────────────────

class TestTray:
    def test_construction_no_exception(self, window):
        assert window is not None

    def test_tray_disabled_when_unavailable(self, qapp):
        from ui.main_window import MainWindow
        with patch(
            "ui.main_window.QSystemTrayIcon.isSystemTrayAvailable",
            return_value=False,
        ):
            w = MainWindow()
            assert w._tray is None  # 미지원 환경에서 조용히 비활성

    def test_setup_tray_when_available(self, qapp):
        from ui.main_window import MainWindow
        with patch(
            "ui.main_window.QSystemTrayIcon.isSystemTrayAvailable",
            return_value=True,
        ):
            w = MainWindow()
            try:
                assert w._tray is not None
            finally:
                w._tray = None
                with patch("ui.main_window.QMessageBox.question",
                           return_value=QMessageBox.StandardButton.Yes):
                    w.close()

    def test_notify_tray_safe_when_no_tray(self, window):
        window._tray = None
        # 예외 없이 무시
        window._notify_tray("t", "m")

    def test_close_without_tray_accepts(self, window):
        window._tray = None
        ev = MagicMock()
        with patch("ui.main_window.QMessageBox.question",
                   return_value=QMessageBox.StandardButton.Yes):
            window.closeEvent(ev)
        ev.accept.assert_called_once()

    def test_close_cancelled_ignores(self, window):
        # 종료 확인에서 [아니오] → 닫기 취소(event.ignore), accept 안 됨.
        window._tray = None
        ev = MagicMock()
        with patch("ui.main_window.QMessageBox.question",
                   return_value=QMessageBox.StandardButton.No):
            window.closeEvent(ev)
        ev.ignore.assert_called_once()
        ev.accept.assert_not_called()

    def test_restore_from_tray_clears_minimized(self, window):
        # showMinimized then restore → not minimized, no exception (offscreen).
        window.show()
        window.showMinimized()
        window._restore_from_tray()
        assert window.isMinimized() is False

    def test_quit_on_last_window_closed_disabled(self, window, qapp):
        # 보조 창(호버 상세/메시지박스/파일 다이얼로그)이 닫혀도 앱이 자동 종료되지
        # 않도록 — 종료는 메인 창 closeEvent 의 명시 quit() 로만.
        assert qapp.quitOnLastWindowClosed() is False

    def test_window_fits_screen_height(self, window, qapp):
        # 시작 크기가 사용 가능한 화면 높이를 넘지 않아야(세로 잘림 방지).
        avail = qapp.primaryScreen().availableGeometry()
        assert window.height() <= avail.height()

    def test_completion_brings_front_and_popup(self, window):
        window._results.add_result({"username": "a"})
        window._scrape_had_error = False
        with patch("ui.main_window.QMessageBox.information") as info:
            window._on_done()
        info.assert_called_once()
        assert window._control._btn_start.isEnabled() is True

    def test_completion_popup_on_error_too(self, window):
        window._scrape_had_error = True
        with patch("ui.main_window.QMessageBox.information") as info:
            window._on_done()
        info.assert_called_once()

    def test_close_quits_even_with_tray(self, window):
        # 닫기(X)는 트레이 유무와 관계없이 완전 종료 (event.accept).
        window._tray = MagicMock()
        window.show()
        ev = MagicMock()
        with patch("ui.main_window.QMessageBox.question",
                   return_value=QMessageBox.StandardButton.Yes):
            window.closeEvent(ev)
        ev.accept.assert_called_once()
        ev.ignore.assert_not_called()

    def test_restore_after_geometry_saved_no_exception(self, window):
        # Saving then restoring geometry round-trips without error.
        window.show()
        window._saved_geometry = window.saveGeometry()
        window._restore_from_tray()
        assert window.isMinimized() is False


# ── 4.3 Resume ──────────────────────────────────────────────────────────────

class TestResume:
    def test_resume_available_when_state_exists(self, window):
        storage.save_state({"keyword": "인턴", "tag_index": 1, "post_index": 2})
        window._refresh_resume()
        assert window._control._btn_resume.isEnabled() is True

    def test_resume_disabled_when_no_state(self, window):
        storage.clear_state()
        window._refresh_resume()
        assert window._control._btn_resume.isEnabled() is False

    def test_start_scrape_clears_state_and_injects_no_resume(self, window):
        storage.save_state({"keyword": "old", "tag_index": 5})
        window._control._search_input.setText("인턴")
        window._browser = MagicMock()   # 임베디드 브라우저 존재로 가정
        params = window._control.collect_params()
        with patch("core.embedded_scraper.EmbeddedScraper") as MockScraper:
            inst = MockScraper.return_value
            inst.isRunning.return_value = False
            window._start_scrape(params)
        # 신규 시작 → state.json 비워짐
        assert storage.load_state() is None
        kwargs = MockScraper.call_args.kwargs
        assert kwargs["resume_state"] is None
        # config 그룹 주입(flow/target)
        for key in ("flow", "target"):
            assert key in kwargs

    def test_resume_injects_resume_state(self, window):
        state = {"keyword": "인턴", "tag_index": 2, "post_index": 3,
                 "collected_count": 7, "seen_usernames": ["a", "b"]}
        storage.save_state(state)
        window._control._search_input.setText("placeholder")
        window._browser = MagicMock()
        with patch("core.embedded_scraper.EmbeddedScraper") as MockScraper:
            inst = MockScraper.return_value
            inst.isRunning.return_value = False
            window._resume_scrape()
        kwargs = MockScraper.call_args.kwargs
        assert kwargs["resume_state"] == state
        # keyword from state overrides search term
        assert kwargs["search_term"] == "인턴"

    def test_resume_noop_without_state(self, window):
        storage.clear_state()
        window._browser = MagicMock()
        with patch("core.embedded_scraper.EmbeddedScraper") as MockScraper:
            window._resume_scrape()
        MockScraper.assert_not_called()


# ── 타겟·제외 계정 양방향 동기화 (컨트롤 패널 ↔ 설정) ────────────────────────

class TestSyncControlPanelAndSettings:
    def test_show_settings_pushes_control_target(self, window):
        # 컨트롤 패널에서 검색 조건을 바꾸고 설정을 열면 target.csv 에 반영된다.
        window._control._btn_keyword.setChecked(True)
        window._control._search_input.setText("취준생")
        window._control._follower_filter.set_values(5000, 50000)
        window.show_settings()
        t = storage.load_target()
        assert t["mode"] == "keyword"
        assert t["keyword"] == "취준생"
        assert int(t["min_followers"]) == 5000
        assert int(t["max_followers"]) == 50000

    def test_show_settings_preserves_target_only_fields(self, window):
        # 컨트롤 패널에 없는 타겟 전용 필드(min_posts 등)는 보존된다.
        storage.save_target({**storage.load_target(), "min_posts": 12,
                             "min_following": 7})
        window._control._search_input.setText("인턴")
        window.show_settings()
        t = storage.load_target()
        assert int(t["min_posts"]) == 12
        assert int(t["min_following"]) == 7
        assert t["keyword"] == "인턴"

    def test_show_main_applies_target_to_control(self, window):
        # 설정에서 저장된 target.csv 가 메인 복귀 시 컨트롤 패널에 반영된다.
        storage.save_target({**storage.load_target(), "mode": "keyword",
                             "keyword": "마케팅", "min_followers": 10000,
                             "max_followers": 100000})
        window.show_main()
        assert window._control._btn_keyword.isChecked() is True
        assert window._control._search_input.text() == "마케팅"
        assert window._control._follower_filter.min_followers == 10000
        assert window._control._follower_filter.max_followers == 100000

    def test_show_main_refreshes_excluded(self, window):
        # 설정에서 추가/삭제된 제외 계정이 메인 복귀 시 위젯에 그대로 반영(치환).
        storage.save_excluded(["spammer", "bot"])
        window.show_main()
        assert set(window._control.excluded_widget.accounts) == {"spammer", "bot"}
        # 삭제도 반영(병합이 아니라 치환)
        storage.save_excluded(["bot"])
        window.show_main()
        assert set(window._control.excluded_widget.accounts) == {"bot"}


class TestEmbeddedTargetFilterInit:
    def test_init_stores_target_filters(self, qapp):
        from core.embedded_scraper import EmbeddedScraper
        s = EmbeddedScraper(
            MagicMock(),
            target={"min_following": 5, "max_following": 500, "min_posts": 30},
        )
        assert s.min_following == 5
        assert s.max_following == 500
        assert s.min_posts == 30


# ── 상세 다이얼로그 (버튼 트리거 + 좌우 분할 + 이전/다음·방향키 네비) ──────────

class TestProfileDetailDialog:
    @pytest.fixture
    def results(self):
        return [
            {"username": "alice", "followers": "1000", "bio": "a"},
            {"username": "bob", "followers": "2000", "bio": "b"},
            {"username": "carol", "followers": "3000", "bio": "c"},
        ]

    def _dlg(self, qapp, results, index=0):
        from ui.dialogs.profile_detail_dialog import ProfileDetailDialog
        return ProfileDetailDialog(results, index)

    def test_renders_initial_index(self, qapp, results):
        d = self._dlg(qapp, results, 1)
        assert "bob" in d._title.text()
        assert d._pos_label.text() == "2 / 3"

    def test_next_prev_navigation(self, qapp, results):
        d = self._dlg(qapp, results, 0)
        assert d._btn_prev.isEnabled() is False   # 첫 항목
        d._next()
        assert "bob" in d._title.text()
        d._next()
        assert "carol" in d._title.text()
        assert d._btn_next.isEnabled() is False    # 마지막
        d._next()                                  # 더 못 감(클램프)
        assert "carol" in d._title.text()
        d._prev()
        assert "bob" in d._title.text()

    def test_arrow_keys_navigate(self, qapp, results):
        from PyQt6.QtGui import QKeyEvent
        from PyQt6.QtCore import QEvent, Qt
        d = self._dlg(qapp, results, 0)
        right = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Right,
                          Qt.KeyboardModifier.NoModifier)
        d.keyPressEvent(right)
        assert "bob" in d._title.text()
        left = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Left,
                         Qt.KeyboardModifier.NoModifier)
        d.keyPressEvent(left)
        assert "alice" in d._title.text()

    def test_empty_results_no_crash(self, qapp):
        d = self._dlg(qapp, [])
        assert d._btn_next.isEnabled() is False
        assert d._btn_prev.isEnabled() is False

    def test_not_always_on_top(self, qapp):
        # URL 이동 시 브라우저가 모달에 가리지 않도록 StaysOnTop 을 두지 않는다.
        from PyQt6.QtCore import Qt
        d = self._dlg(qapp, [{"username": "alice"}], 0)
        assert not (d.windowFlags() & Qt.WindowType.WindowStaysOnTopHint)

    def test_url_buttons_copy_and_state(self, qapp):
        results = [
            {"username": "alice", "profile_url": "https://insta/alice"},
            {"username": "bob"},  # URL 없음
        ]
        d = self._dlg(qapp, results, 0)
        assert d._btn_copy.isEnabled() is True
        assert d._btn_open.isEnabled() is True
        d._copy_url()
        from PyQt6.QtWidgets import QApplication
        assert QApplication.clipboard().text() == "https://insta/alice"
        assert d._btn_copy.text() == "복사됨 ✓"
        # URL 없는 항목으로 이동 → 버튼 비활성 + 라벨 초기화
        d._next()
        assert d._btn_copy.isEnabled() is False
        assert d._btn_open.isEnabled() is False
        assert d._btn_copy.text() == "URL 복사"

    def test_profile_url_not_shown_as_field(self, qapp):
        # 프로필 URL 은 텍스트 필드로 노출하지 않는다(버튼으로만).
        from ui.dialogs.profile_detail_dialog import _FIELDS
        assert "profile_url" not in [key for _, key in _FIELDS]


class TestResultsPanelDetailButton:
    @pytest.fixture
    def panel(self, qapp):
        from ui.panels.results_panel import ResultsPanel
        return ResultsPanel()

    def test_detail_cell_is_open_text(self, panel):
        panel.add_result({"username": "alice", "followers": "10"})
        # '상세'(col 6)는 버튼이 아니라 '열기' 글자 셀, 클릭 시 상세창.
        assert panel._table.cellWidget(0, 6) is None
        assert panel._table.item(0, 6).text() == "열기"

    def test_cell_click_opens_detail(self, panel):
        panel.add_result({"username": "alice", "followers": "10"})
        panel.add_result({"username": "bob", "followers": "20"})
        panel._on_cell_clicked(1, 6)   # 상세 컬럼 클릭
        assert panel._detail_dialog is not None
        assert "bob" in panel._detail_dialog._title.text()
        panel._detail_dialog.close()

    def test_cell_click_other_column_no_dialog(self, panel):
        panel.add_result({"username": "alice", "followers": "10"})
        panel._on_cell_clicked(0, 2)   # 팔로워 컬럼 → 상세창 안 뜸
        assert panel._detail_dialog is None

    def test_open_detail_creates_dialog(self, panel):
        panel.add_result({"username": "alice", "followers": "10"})
        panel.add_result({"username": "bob", "followers": "20"})
        panel._open_detail(1)
        assert panel._detail_dialog is not None
        assert "bob" in panel._detail_dialog._title.text()
        panel._detail_dialog.close()

    def test_open_detail_out_of_range_noop(self, panel):
        panel._open_detail(5)  # 결과 없음 → 예외 없이 무시
        assert panel._detail_dialog is None


# ── 4.4 Blocked + Skip ───────────────────────────────────────────────────────

class TestBlockedAndSkip:
    def test_skip_counter_accumulates(self, window):
        window._skip_count = 0
        window._on_skip("alice")
        window._on_skip("bob")
        window._on_skip("carol")
        assert window._skip_count == 3
        assert "중복skip 3" in window._results._progress_label.text()

    def test_blocked_stops_scraper(self, window):
        scraper = MagicMock()
        window._scraper = scraper
        with patch("ui.main_window.QMessageBox.warning"):
            window._on_blocked()
        scraper.stop.assert_called_once()

    def test_blocked_no_scraper_no_exception(self, window):
        window._scraper = None
        with patch("ui.main_window.QMessageBox.warning"):
            window._on_blocked()  # must not raise

    def test_skip_writes_to_run_logger(self, window):
        logger = MagicMock()
        window._run_logger = logger
        window._on_skip("alice")
        logger.write.assert_called_once()


# ── Fix-2 C: 로그인 완료 버튼 제거 ───────────────────────────────────────────

class TestLoginButtonRemoved:
    def test_control_panel_has_no_login_button(self, window):
        # The redundant in-panel login button is gone; LoginWaitDialog confirms.
        assert not hasattr(window._control, "_btn_login_done")

    def test_set_running_waiting_login_no_exception(self, window):
        # waiting_login flag still accepted (signal compat) but toggles no button.
        window._control.set_running(True, waiting_login=True)
        window._control.set_running(False)
        assert window._control._btn_start.isEnabled() is True

    def test_on_waiting_login_shows_banner(self, window):
        # 모달 대신 results_panel 내 로그인 배너가 표시된다.
        window._on_waiting_login()
        assert window._results._login_banner.isHidden() is False
        # cleanup
        window._results.hide_login_banner()


# ── 4.5 Progress label + log color ──────────────────────────────────────────

class TestProgressLabel:
    @pytest.fixture
    def panel(self, qapp):
        from ui.panels.results_panel import ResultsPanel
        return ResultsPanel()

    def test_label_reflects_collected_and_skip(self, panel):
        panel.add_result({"username": "a", "followers": "10"})
        panel.add_result({"username": "b", "followers": "20"})
        panel.set_skip_count(4)
        text = panel._progress_label.text()
        assert "수집 2" in text
        assert "중복skip 4" in text

    def test_set_step_in_label(self, panel):
        panel.set_step("태그 1/3")
        assert "태그 1/3" in panel._progress_label.text()

    def test_collected_count(self, panel):
        assert panel.collected_count() == 0
        panel.add_result({"username": "a"})
        assert panel.collected_count() == 1

    def test_reset_clears_label(self, panel):
        panel.add_result({"username": "a"})
        panel.set_skip_count(3)
        panel.reset()
        assert panel.collected_count() == 0
        assert "수집 0" in panel._progress_label.text()
        assert "중복skip 0" in panel._progress_label.text()

    @pytest.mark.parametrize("msg, expected_attr", [
        ("[OK] saved", "green"),
        ("[ERROR] boom", "red"),
        ("[에러] 오류", "red"),
        ("[blocked] 차단", "red"),
        ("[wait] login", "amber"),
        ("[skip] dup", "amber"),
        ("[step] 태그", "accent_light"),
        ("plain info", "muted2"),
    ])
    def test_log_color_by_prefix(self, panel, msg, expected_attr):
        from design.tokens import Colors as Cc
        assert panel.log_color(msg) == getattr(Cc, expected_attr)
