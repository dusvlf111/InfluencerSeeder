"""SettingsView (Push3) — 기본 설정 탭 populate/collect/save_all 검증.

pytest-qt 미설치: tests/conftest.py 의 offscreen `qapp` session fixture 를 사용해
위젯을 직접 생성하고 순수 로직(populate/collect/save_all)만 검증한다.
실제 클릭/이벤트루프/네트워크는 호출하지 않는다.
"""
import pytest

import core.storage as storage
from ui.settings_view import SettingsView, _as_bool


@pytest.fixture
def view(qapp, monkeypatch, tmp_path):
    monkeypatch.setattr(storage, "DATA_DIR", tmp_path)
    v = SettingsView()
    return v


class TestAsBool:
    @pytest.mark.parametrize("val,expected", [
        ("true", True), ("True", True), ("TRUE", True), (" true ", True),
        ("false", False), ("False", False), ("", False), ("yes", False),
        (True, True), (False, False),
    ])
    def test_as_bool(self, val, expected):
        assert _as_bool(val) is expected


class TestTabsAndPopulate:
    def test_load_no_exception(self, view):
        view.load()  # must not raise

    def test_tabs_present(self, view):
        labels = [view._tabs.tabText(i) for i in range(view._tabs.count())]
        for name in ("Web", "Delays", "Flow", "Target", "Excluded"):
            assert name in labels

    def test_existing_selectors_tab_kept(self, view):
        labels = [view._tabs.tabText(i) for i in range(view._tabs.count())]
        assert "Selectors" in labels

    def test_web_widgets_exist_and_defaults(self, view):
        view.load()
        # headless default false → unchecked
        assert view._w_headless.isChecked() is False
        assert view._w_randomize_window.isChecked() is True
        assert view._w_browser.currentText() == "chrome"
        assert view._w_window_width.value() == 1280
        assert view._w_window_height.value() == 900
        assert view._w_locale.text() == "ko-KR"
        assert view._w_implicit_wait.value() == 5
        assert view._w_page_load_timeout.value() == 30

    def test_flow_widgets_defaults(self, view):
        view.load()
        assert view._fl_max_tags.value() == 3
        assert view._fl_tag_start_index.value() == 0
        assert view._fl_posts_per_tag.value() == 5
        assert view._fl_scroll_max_attempts.value() == 15
        assert view._fl_skip_visited_profile.isChecked() is True
        assert view._fl_stop_on_consecutive_miss.value() == 10

    def test_target_widgets_defaults(self, view):
        view.load()
        assert view._t_min_followers.value() == 0
        assert view._t_max_followers.value() == 0
        assert view._t_mode.currentText() == "hashtag"

    def test_delays_table_has_scroll_and_typing_rows(self, view):
        view.load()
        labels = [
            view._delay_table.item(r, 0).text()
            for r in range(view._delay_table.rowCount())
        ]
        assert any("Scroll" in x for x in labels)
        assert any("Typing" in x for x in labels)

    def test_delays_populated_from_defaults(self, view):
        view.load()
        # step1 default (1.0, 2.5)
        assert float(view._delay_table.item(0, 1).text()) == 1.0
        assert float(view._delay_table.item(0, 2).text()) == 2.5


class TestSaveAll:
    def test_round_trip_web(self, view, tmp_path):
        view.load()
        view._w_headless.setChecked(True)
        view._w_window_width.setValue(1024)
        view._w_locale.setText("en-US")
        view._save_all()
        web = storage.load_web()
        assert _as_bool(web["headless"]) is True
        assert int(web["window_width"]) == 1024
        assert web["locale"] == "en-US"

    def test_round_trip_flow(self, view):
        view.load()
        view._fl_max_tags.setValue(7)
        view._fl_skip_visited_profile.setChecked(False)
        view._save_all()
        flow = storage.load_flow()
        assert int(flow["max_tags"]) == 7
        assert _as_bool(flow["skip_visited_profile"]) is False

    def test_round_trip_target(self, view):
        view.load()
        view._t_min_followers.setValue(5000)
        view._t_max_followers.setValue(50000)
        view._t_keyword.setText("seoul")
        view._t_mode.setCurrentText("keyword")
        view._save_all()
        target = storage.load_target()
        assert int(target["min_followers"]) == 5000
        assert int(target["max_followers"]) == 50000
        assert target["keyword"] == "seoul"
        assert target["mode"] == "keyword"

    def test_round_trip_delays(self, view):
        view.load()
        view._delay_table.item(0, 1).setText("3.3")
        view._delay_table.item(0, 2).setText("4.4")
        view._save_all()
        delays = storage.load_delays()
        assert delays["step1"] == (3.3, 4.4)

    def test_collect_delays_is_dict_of_pairs(self, view):
        view.load()
        d = view._collect_delays()
        assert isinstance(d, dict)
        assert "scroll" in d and "typing_char" in d
        for k, v in d.items():
            assert isinstance(v, tuple) and len(v) == 2

    def test_round_trip_excluded(self, view):
        view.load()
        view._excl_input.setText("alice, @bob")
        view._add_excluded()
        view._save_all()
        excluded = storage.load_excluded()
        assert "alice" in excluded
        assert "bob" in excluded

    def test_bad_delay_input_falls_back_to_default(self, view):
        view.load()
        view._delay_table.item(0, 1).setText("not-a-number")
        view._delay_table.item(0, 2).setText("")
        d = view._collect_delays()  # must not raise
        defaults = storage.delay_defaults()
        assert d["step1"] == defaults["step1"]

    def test_save_all_emits_back_requested(self, view):
        view.load()
        fired = []
        view.back_requested.connect(lambda: fired.append(True))
        view._save_all()
        assert fired == [True]

    def test_save_all_creates_all_csvs(self, view, tmp_path):
        view.load()
        view._save_all()
        for name in ("web.csv", "delays.csv", "flow.csv", "target.csv", "excluded.csv"):
            assert (tmp_path / name).exists()
