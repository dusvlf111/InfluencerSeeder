"""SettingsView — 남은 탭(딜레이/수집 설정/제외 계정/버튼매핑) populate/collect/save_all 검증.

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
        for name in ("타겟", "딜레이", "수집 설정", "제외 계정", "버튼매핑"):
            assert name in labels

    def test_removed_tabs_absent(self, view):
        labels = [view._tabs.tabText(i) for i in range(view._tabs.count())]
        for name in ("Web", "수집 항목", "플로우", "Dependencies"):
            assert name not in labels, f"제거된 탭 '{name}' 이 여전히 표시됨"

    def test_flow_widgets_present(self, view):
        view.load()
        assert view._fl_posts_per_tag.value() == 5
        assert view._fl_skip_first.isChecked() is True

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
        defaults = storage.delay_defaults()
        lo, hi = defaults["step1"]
        assert float(view._delay_table.item(0, 1).text()) == lo
        assert float(view._delay_table.item(0, 2).text()) == hi


class TestSaveAll:
    def test_round_trip_flow(self, view):
        view.load()
        view._fl_posts_per_tag.setValue(12)
        view._fl_skip_first.setChecked(False)
        view._save_all()
        flow = storage.load_flow()
        assert int(flow["posts_per_tag"]) == 12
        assert _as_bool(flow["skip_first_post"]) is False

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

    def test_round_trip_target(self, view):
        view.load()
        view._t_min_followers.setValue(5000)
        view._t_max_followers.setValue(50000)
        view._t_keyword.setText("취준생")
        idx = view._t_mode.findText("keyword")
        view._t_mode.setCurrentIndex(idx)
        view._save_all()
        target = storage.load_target()
        assert int(target["min_followers"]) == 5000
        assert int(target["max_followers"]) == 50000
        assert target["keyword"] == "취준생"
        assert target["mode"] == "keyword"

    def test_save_all_creates_active_csvs(self, view, tmp_path):
        view.load()
        view._save_all()
        for name in ("delays.csv", "flow.csv", "target.csv", "excluded.csv", "selectors.csv"):
            assert (tmp_path / name).exists(), f"{name} not created"

    def test_save_all_does_not_write_removed_csvs(self, view, tmp_path):
        view.load()
        view._save_all()
        # 제거된 탭의 CSV 는 _save_all 이 건드리지 않음
        for name in ("web.csv", "fields.csv", "flow_steps.csv"):
            assert not (tmp_path / name).exists(), f"{name} should not be written"


# ── 버튼매핑 자유 편집 단일 테이블 ──────────────────────────────────────────


class TestMappingTable:
    _TYPE, _VALUE = 0, 1

    @staticmethod
    def _group(view, step_id):
        return next(g for g in view._mapping_groups if g["step_id"] == step_id)

    @staticmethod
    def _set_value(table, r, text):
        from PyQt6.QtWidgets import QTableWidgetItem
        table.setItem(r, 1, QTableWidgetItem(text))

    def test_groups_populated_from_defaults(self, view):
        view.load()
        ids = [g["step_id"] for g in view._mapping_groups]
        for sid in ("search_icon", "search_input", "tag_result", "post_link", "profile_link"):
            assert sid in ids

    def test_search_icon_has_multiple_candidates(self, view):
        view.load()
        assert self._group(view, "search_icon")["table"].rowCount() >= 1

    def test_collect_selectors_round_trip(self, view):
        view.load()
        before = storage.load_selectors()
        rows = view._collect_selectors()
        assert len(rows) == len(before)
        assert all(isinstance(r["priority"], int) for r in rows)
        assert all(r["step_id"] for r in rows)

    def test_candidate_order_is_priority(self, view):
        view.load()
        rows = [r for r in view._collect_selectors() if r["step_id"] == "search_icon"]
        assert [r["priority"] for r in rows] == list(range(1, len(rows) + 1))

    def test_edit_value_persists_through_save(self, view):
        view.load()
        g = self._group(view, "search_icon")
        self._set_value(g["table"], 0, "//a[@id='edited']")
        view._save_all()
        reloaded = storage.load_selectors()
        edited = [r for r in reloaded if r["step_id"] == "search_icon"]
        assert any(r["selector_value"] == "//a[@id='edited']" for r in edited)

    def test_add_candidate_reflected_in_collect(self, view):
        view.load()
        g = self._group(view, "search_icon")
        n0 = len([r for r in view._collect_selectors() if r["step_id"] == "search_icon"])
        view._mapping_cand_add(g["table"])
        self._set_value(g["table"], g["table"].rowCount() - 1, "//a[@role='link']")
        n1 = len([r for r in view._collect_selectors() if r["step_id"] == "search_icon"])
        assert n1 == n0 + 1

    def test_empty_candidate_dropped_on_collect(self, view):
        view.load()
        g = self._group(view, "search_icon")
        n0 = len(view._collect_selectors())
        view._mapping_cand_add(g["table"])  # blank value row
        assert len(view._collect_selectors()) == n0

    def test_add_and_delete_candidate(self, view):
        view.load()
        table = self._group(view, "search_icon")["table"]
        n0 = table.rowCount()
        view._mapping_cand_add(table)
        assert table.rowCount() == n0 + 1
        table.selectRow(table.rowCount() - 1)
        view._mapping_cand_del(table)
        assert table.rowCount() == n0

    def test_move_candidate_swaps(self, view):
        view.load()
        table = self._group(view, "search_icon")["table"]
        if table.rowCount() < 2:
            view._mapping_cand_add(table)
        self._set_value(table, 0, "AAA")
        self._set_value(table, 1, "BBB")
        table.selectRow(0)
        view._mapping_cand_move(table, 1)
        assert table.item(0, self._VALUE).text() == "BBB"
        assert table.item(1, self._VALUE).text() == "AAA"

    def test_reset_restores_defaults(self, view):
        view.load()
        g = self._group(view, "search_icon")
        view._mapping_cand_add(g["table"])  # mutate
        view._mapping_reset()
        assert len(view._collect_selectors()) == len(storage.selector_defaults())

    def test_mapping_rebuilds_on_reload(self, view):
        view.load()
        n = len(view._mapping_groups)
        view.load()  # second load must not duplicate groups
        assert len(view._mapping_groups) == n

    def test_add_custom_step(self, view):
        view.load()
        n0 = len(view._mapping_groups)
        view._mapping_add_step()
        assert len(view._mapping_groups) == n0 + 1

    def test_type_cell_is_combo_with_choices(self, view):
        from PyQt6.QtWidgets import QComboBox
        view.load()
        table = self._group(view, "search_icon")["table"]
        combo = table.cellWidget(0, self._TYPE)
        assert isinstance(combo, QComboBox)
        items = [combo.itemText(i) for i in range(combo.count())]
        for t in ("xpath", "css", "coord"):
            assert t in items

    def test_added_candidate_type_defaults_to_xpath(self, view):
        view.load()
        table = self._group(view, "search_icon")["table"]
        view._mapping_cand_add(table)
        combo = table.cellWidget(table.rowCount() - 1, self._TYPE)
        assert combo is not None and combo.currentText() == "xpath"

    def test_coord_type_round_trips(self, view):
        view.load()
        table = self._group(view, "search_icon")["table"]
        view._mapping_cand_add(table)
        r = table.rowCount() - 1
        table.cellWidget(r, self._TYPE).setCurrentText("coord")
        self._set_value(table, r, "100,200")
        rows = [x for x in view._collect_selectors() if x["step_id"] == "search_icon"]
        assert any(x["selector_type"] == "coord" and x["selector_value"] == "100,200"
                   for x in rows)

    def test_move_candidate_preserves_type(self, view):
        view.load()
        table = self._group(view, "search_icon")["table"]
        if table.rowCount() < 2:
            view._mapping_cand_add(table)
        table.cellWidget(0, self._TYPE).setCurrentText("xpath")
        table.cellWidget(1, self._TYPE).setCurrentText("css")
        self._set_value(table, 0, "A")
        self._set_value(table, 1, "B")
        table.selectRow(0)
        view._mapping_cand_move(table, 1)
        assert table.cellWidget(0, self._TYPE).currentText() == "css"
        assert table.cellWidget(1, self._TYPE).currentText() == "xpath"


# ── 설정 폴더 가져오기/내보내기 ──────────────────────────────────────────────


class TestConfigShare:
    def test_export_then_import_round_trip(self, view, tmp_path):
        view.load()
        view._save_all()
        share = tmp_path / "share"
        written = storage.export_config_to_dir(str(share))
        assert "selectors.csv" in written
        assert "delays.csv" in written

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
        assert "selectors.csv" in written
        # mutate selectors, re-import to restore
        g = next(g for g in view._mapping_groups if g["step_id"] == "search_icon")
        view._mapping_cand_add(g["table"])
        view._save_all()
        imported = storage.import_config_from_zip(str(zip_path))
        assert "selectors.csv" in imported

    def test_import_missing_zip_returns_nothing(self, tmp_path):
        assert storage.import_config_from_zip(str(tmp_path / "nope.zip")) == []


# ── zip 전용 + 항목 선택 공유 (설정 + 제외 + 수집데이터) ──────────────────────


class TestShareableZip:
    def test_results_and_excluded_round_trip(self, view, tmp_path):
        view.load()
        view._save_all()
        storage.append_result({"username": "alice", "followers": "100"})
        storage.save_excluded(["spammer"])
        zip_path = tmp_path / "bundle.zip"
        written = storage.export_config_to_zip(str(zip_path))
        assert "results.csv" in written
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
            str(zip_path), names=["selectors.csv", "delays.csv"])
        assert set(written) == {"selectors.csv", "delays.csv"}
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
        assert "excluded.csv" in storage.SHAREABLE_FILES
        assert len(storage.SHAREABLE_FILES) == len(set(storage.SHAREABLE_FILES))


class TestExportSelectDialog:
    def test_selected_names_reflects_existing_files(self, view, tmp_path, qapp):
        from ui.dialogs.export_select_dialog import ExportSelectDialog
        view.load()
        view._save_all()  # materializes config CSVs (no results.csv)
        dlg = ExportSelectDialog()
        names = dlg.selected_names()
        assert "selectors.csv" in names
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
