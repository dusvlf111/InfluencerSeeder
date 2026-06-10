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

    def test_mapping_and_flow_tabs_present(self, view):
        # P3/P4: "Selectors" 탭은 "버튼매핑" 카드 탭으로 교체되고 "플로우" 탭이 추가됨.
        labels = [view._tabs.tabText(i) for i in range(view._tabs.count())]
        assert "버튼매핑" in labels
        assert "플로우" in labels
        assert "Selectors" not in labels

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

    def test_save_all_writes_flow_steps_csv(self, view, tmp_path):
        view.load()
        view._save_all()
        assert (tmp_path / "flow_steps.csv").exists()
        assert (tmp_path / "selectors.csv").exists()


# ── A: 버튼매핑 자유 편집 단일 테이블 ──────────────────────────────────────────


class TestMappingTable:
    # column indices for the free-form table: Step ID | Step Name | Priority | Type | Value
    _SID, _NAME, _PRIO, _TYPE, _VALUE = 0, 1, 2, 3, 4

    def test_single_table_populated_from_defaults(self, view):
        view.load()
        before = storage.load_selectors()
        # one row per selector candidate (no per-step cards).
        assert view._mapping_table.rowCount() == len(before)
        # first column is the (free-form) step_id.
        first = view._mapping_table.item(0, self._SID).text()
        assert first == before[0]["step_id"]

    def test_collect_selectors_round_trip(self, view):
        view.load()
        before = storage.load_selectors()
        rows = view._collect_selectors()
        # same total candidate count, priority is int, step_id preserved.
        assert len(rows) == len(before)
        assert all(isinstance(r["priority"], int) for r in rows)
        assert all(r["step_id"] for r in rows)

    def test_edit_value_persists_through_save(self, view):
        view.load()
        from PyQt6.QtWidgets import QTableWidgetItem
        table = view._mapping_table
        # find the first search_icon row and edit its value.
        target = next(
            r for r in range(table.rowCount())
            if table.item(r, self._SID).text() == "search_icon"
        )
        table.setItem(target, self._VALUE, QTableWidgetItem("//a[@id='edited']"))
        view._save_all()
        reloaded = storage.load_selectors()
        edited = [r for r in reloaded if r["step_id"] == "search_icon"]
        assert any(r["selector_value"] == "//a[@id='edited']" for r in edited)

    def test_free_form_step_id_round_trip(self, view):
        view.load()
        from PyQt6.QtWidgets import QTableWidgetItem
        table = view._mapping_table
        view._mapping_add_row()
        r = table.rowCount() - 1
        table.setItem(r, self._SID, QTableWidgetItem("my_custom_step"))
        table.setItem(r, self._NAME, QTableWidgetItem("커스텀"))
        table.setItem(r, self._PRIO, QTableWidgetItem("2"))
        table.setItem(r, self._TYPE, QTableWidgetItem("css"))
        table.setItem(r, self._VALUE, QTableWidgetItem("div.custom"))
        view._save_all()
        reloaded = storage.load_selectors()
        custom = [r for r in reloaded if r["step_id"] == "my_custom_step"]
        assert len(custom) == 1
        assert custom[0]["selector_value"] == "div.custom"
        assert custom[0]["selector_type"] == "css"
        assert custom[0]["priority"] == 2

    def test_empty_step_id_row_dropped_on_collect(self, view):
        view.load()
        n0 = len(view._collect_selectors())
        view._mapping_add_row()  # blank step_id row
        assert len(view._collect_selectors()) == n0

    def test_add_and_delete_row(self, view):
        view.load()
        table = view._mapping_table
        n0 = table.rowCount()
        view._mapping_add_row()
        assert table.rowCount() == n0 + 1
        table.selectRow(table.rowCount() - 1)
        view._mapping_del_row()
        assert table.rowCount() == n0

    def test_move_row_swaps(self, view):
        view.load()
        from PyQt6.QtWidgets import QTableWidgetItem
        table = view._mapping_table
        table.setItem(0, self._VALUE, QTableWidgetItem("AAA"))
        table.setItem(1, self._VALUE, QTableWidgetItem("BBB"))
        table.selectRow(0)
        view._mapping_move_row(1)
        assert table.item(0, self._VALUE).text() == "BBB"
        assert table.item(1, self._VALUE).text() == "AAA"

    def test_reset_restores_defaults(self, view):
        view.load()
        table = view._mapping_table
        view._mapping_add_row()  # mutate
        view._mapping_reset()
        assert table.rowCount() == len(storage.selector_defaults())

    def test_mapping_rebuilds_on_reload(self, view):
        view.load()
        n = view._mapping_table.rowCount()
        view.load()  # second load must not duplicate rows
        assert view._mapping_table.rowCount() == n


# ── Fix-2 B: 수집 항목 탭 ───────────────────────────────────────────────────────


class TestFieldsTab:
    def test_tab_present(self, view):
        labels = [view._tabs.tabText(i) for i in range(view._tabs.count())]
        assert "수집 항목" in labels

    def test_username_always_collected_and_disabled(self, view):
        view.load()
        assert view._cf_username.isChecked() is True
        assert view._cf_username.isEnabled() is False

    def test_checkboxes_default_checked(self, view):
        view.load()
        for field in storage.COLLECT_FIELDS:
            assert getattr(view, f"_cf_{field}").isChecked() is True

    def test_collect_fields_settings_shape(self, view):
        view.load()
        d = view._collect_fields_settings()
        assert set(d.keys()) == set(storage.COLLECT_FIELDS)
        assert all(isinstance(v, bool) for v in d.values())

    def test_round_trip_through_save(self, view):
        view.load()
        view._cf_followers.setChecked(False)
        view._cf_bio.setChecked(False)
        view._save_all()
        f = storage.load_fields()
        assert f["followers"] is False
        assert f["bio"] is False
        assert f["full_name"] is True

    def test_populate_reflects_saved(self, view):
        storage.save_fields({"website": False})
        view.load()
        assert view._cf_website.isChecked() is False
        assert view._cf_followers.isChecked() is True


# ── P4: 플로우 빌더 ────────────────────────────────────────────────────────────


class TestFlowBuilder:
    def test_flow_table_populated_from_defaults(self, view):
        view.load()
        assert view._flow_table.rowCount() == len(storage.flow_steps_defaults())

    def test_collect_flow_steps_shape(self, view):
        view.load()
        rows = view._collect_flow_steps()
        assert rows
        first = rows[0]
        for key in ("order", "phase", "step_name", "action", "selector_ref", "param", "enabled"):
            assert key in first
        assert all(isinstance(r["enabled"], bool) for r in rows)
        assert all(isinstance(r["order"], int) for r in rows)

    def test_collect_matches_defaults_actions(self, view):
        view.load()
        rows = view._collect_flow_steps()
        actions = [r["action"] for r in rows]
        assert actions == [r["action"] for r in storage.flow_steps_defaults()]

    def test_add_row_increments(self, view):
        view.load()
        n0 = view._flow_table.rowCount()
        view._flow_add_row()
        assert view._flow_table.rowCount() == n0 + 1
        # order renumbered consecutively
        last = view._flow_table.item(view._flow_table.rowCount() - 1, 0).text()
        assert last == str(view._flow_table.rowCount())

    def test_delete_row(self, view):
        view.load()
        n0 = view._flow_table.rowCount()
        view._flow_table.selectRow(0)
        view._flow_del_row()
        assert view._flow_table.rowCount() == n0 - 1

    def test_move_row_reorders_actions(self, view):
        view.load()
        before = [r["action"] for r in view._collect_flow_steps()]
        view._flow_table.selectRow(0)
        view._flow_move_row(1)
        after = [r["action"] for r in view._collect_flow_steps()]
        assert after[0] == before[1]
        assert after[1] == before[0]

    def test_reset_to_defaults(self, view):
        view.load()
        view._flow_add_row()
        view._flow_reset()
        assert view._flow_table.rowCount() == len(storage.flow_steps_defaults())

    def test_round_trip_flow_steps_through_save(self, view):
        view.load()
        # add a wait step, then save and reload
        view._flow_add_row()
        view._save_all()
        reloaded = storage.load_flow_steps()
        # defaults(10) + 1 added
        assert len(reloaded) == len(storage.flow_steps_defaults()) + 1
        assert reloaded[-1]["action"] in storage.FLOW_ACTIONS

    def test_disabled_step_persists(self, view):
        from PyQt6.QtWidgets import QCheckBox
        view.load()
        wrap = view._flow_table.cellWidget(0, 6)
        chk = wrap.findChild(QCheckBox)
        chk.setChecked(False)
        view._save_all()
        reloaded = storage.load_flow_steps()
        assert reloaded[0]["enabled"] is False

    def test_selector_ref_choices_are_distinct_step_ids(self, view):
        view.load()
        choices = view._selector_ref_choices()
        assert "search_icon" in choices
        assert "post_link" in choices
        assert len(choices) == len(set(choices))


# ── P5: 설정 폴더 가져오기/내보내기 (storage 헬퍼 경로 주입) ──────────────────────


class TestConfigShare:
    def test_export_then_import_round_trip(self, view, tmp_path):
        view.load()
        view._save_all()
        share = tmp_path / "share"
        written = storage.export_config_to_dir(str(share))
        assert "flow_steps.csv" in written
        assert "selectors.csv" in written
        # mutate flow then re-import from the exported folder
        view._flow_reset()
        view._flow_add_row()
        view._save_all()
        imported = storage.import_config_from_dir(str(share))
        assert "flow_steps.csv" in imported
        # reload reflects the imported (original) flow length
        view.load()
        assert view._flow_table.rowCount() == len(storage.flow_steps_defaults())

    def test_import_empty_folder_returns_nothing(self, view, tmp_path):
        empty = tmp_path / "empty"
        empty.mkdir()
        imported = storage.import_config_from_dir(str(empty))
        assert imported == []

    def test_export_then_import_zip_round_trip(self, view, tmp_path):
        view.load()
        view._save_all()
        zip_path = tmp_path / "config.zip"
        written = storage.export_config_to_zip(str(zip_path))
        assert zip_path.exists()
        assert "flow_steps.csv" in written
        assert "selectors.csv" in written
        # mutate flow then re-import from the exported zip
        view._flow_reset()
        view._flow_add_row()
        view._save_all()
        imported = storage.import_config_from_zip(str(zip_path))
        assert "flow_steps.csv" in imported
        view.load()
        assert view._flow_table.rowCount() == len(storage.flow_steps_defaults())

    def test_import_missing_zip_returns_nothing(self, tmp_path):
        assert storage.import_config_from_zip(str(tmp_path / "nope.zip")) == []


# ── Fix-2 D: zip 전용 + 항목 선택 공유 (설정 + 제외 + 수집데이터) ─────────────────


class TestShareableZip:
    def test_results_and_fields_round_trip(self, view, tmp_path):
        view.load()
        view._save_all()
        # collected data + a couple of excluded accounts
        storage.append_result({"username": "alice", "followers": "100"})
        storage.save_excluded(["spammer"])
        zip_path = tmp_path / "bundle.zip"
        written = storage.export_config_to_zip(str(zip_path))
        assert "results.csv" in written
        assert "fields.csv" in written
        assert "excluded.csv" in written
        # wipe + re-import → data restored.
        (tmp_path / "results.csv").unlink()
        assert storage.load_results() == []
        imported = storage.import_config_from_zip(str(zip_path))
        assert "results.csv" in imported
        rows = storage.load_results()
        assert any(r["username"] == "alice" for r in rows)

    def test_export_only_selected_names(self, view, tmp_path):
        view.load()
        view._save_all()
        storage.append_result({"username": "bob", "followers": "5"})
        zip_path = tmp_path / "sel.zip"
        written = storage.export_config_to_zip(
            str(zip_path), names=["selectors.csv", "fields.csv"])
        assert set(written) == {"selectors.csv", "fields.csv"}
        assert "results.csv" not in written

    def test_results_excluded_when_absent(self, view, tmp_path):
        view.load()
        view._save_all()  # no results.csv written
        zip_path = tmp_path / "noresults.zip"
        written = storage.export_config_to_zip(str(zip_path))
        assert "results.csv" not in written
        assert "selectors.csv" in written

    def test_shareable_files_includes_data_and_config(self):
        assert "results.csv" in storage.SHAREABLE_FILES
        assert "fields.csv" in storage.SHAREABLE_FILES
        assert "excluded.csv" in storage.SHAREABLE_FILES
        # no duplicates
        assert len(storage.SHAREABLE_FILES) == len(set(storage.SHAREABLE_FILES))


class TestExportSelectDialog:
    def test_selected_names_reflects_existing_files(self, view, tmp_path, qapp):
        from ui.dialogs.export_select_dialog import ExportSelectDialog
        view.load()
        view._save_all()  # materializes config CSVs (no results.csv)
        dlg = ExportSelectDialog()
        names = dlg.selected_names()
        # config files exist and are pre-checked; results.csv absent → unchecked.
        assert "selectors.csv" in names
        assert "fields.csv" in names
        assert "results.csv" not in names
        dlg.close()

    def test_select_none_then_all(self, view, tmp_path, qapp):
        from ui.dialogs.export_select_dialog import ExportSelectDialog
        view.load()
        view._save_all()
        dlg = ExportSelectDialog()
        dlg._set_all(False)
        assert dlg.selected_names() == []
        dlg._set_all(True)
        # only existing files become checked
        assert "selectors.csv" in dlg.selected_names()
        dlg.close()

    def test_results_checkbox_enabled_when_present(self, view, tmp_path, qapp):
        from ui.dialogs.export_select_dialog import ExportSelectDialog
        view.load()
        view._save_all()
        storage.append_result({"username": "carol", "followers": "9"})
        dlg = ExportSelectDialog()
        assert "results.csv" in dlg.selected_names()
        dlg.close()
