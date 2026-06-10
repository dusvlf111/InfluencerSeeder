import csv

import pytest

import core.storage as storage


@pytest.fixture(autouse=True)
def tmp_data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "DATA_DIR", tmp_path)
    yield tmp_path


# ── flow_steps.csv ──────────────────────────────────────────────────────────────

class TestFlowSteps:
    def test_load_returns_defaults_when_no_file(self):
        rows = storage.load_flow_steps()
        assert rows == storage.flow_steps_defaults()
        assert rows[0]["action"] == "click"
        assert rows[0]["enabled"] is True

    def test_load_creates_file(self, tmp_data_dir):
        storage.load_flow_steps()
        assert (tmp_data_dir / "flow_steps.csv").exists()

    def test_default_steps_use_known_actions(self):
        for row in storage.flow_steps_defaults():
            assert row["action"] in storage.FLOW_ACTIONS

    def test_roundtrip_preserves_order_and_enabled(self):
        rows = storage.flow_steps_defaults()
        rows[9]["enabled"] = False            # disable go_back
        storage.save_flow_steps(rows)
        loaded = storage.load_flow_steps()
        assert [r["order"] for r in loaded] == list(range(1, 11))
        assert loaded[9]["action"] == "go_back"
        assert loaded[9]["enabled"] is False

    def test_load_sorts_by_order(self):
        storage.save_flow_steps([
            {"order": 3, "phase": "per_post", "step_name": "c", "action": "save", "selector_ref": "", "param": "", "enabled": True},
            {"order": 1, "phase": "per_tag", "step_name": "a", "action": "click", "selector_ref": "search_icon", "param": "", "enabled": True},
            {"order": 2, "phase": "per_post", "step_name": "b", "action": "extract", "selector_ref": "", "param": "", "enabled": True},
        ])
        loaded = storage.load_flow_steps()
        assert [r["step_name"] for r in loaded] == ["a", "b", "c"]

    def test_unknown_action_row_dropped(self, tmp_data_dir):
        path = tmp_data_dir / "flow_steps.csv"
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["order", "phase", "step_name", "action", "selector_ref", "param", "enabled"])
            w.writerow([1, "per_tag", "ok", "click", "search_icon", "", "true"])
            w.writerow([2, "per_tag", "bogus", "frobnicate", "", "", "true"])
        loaded = storage.load_flow_steps()
        assert [r["action"] for r in loaded] == ["click"]

    def test_enabled_string_variants_normalized(self, tmp_data_dir):
        path = tmp_data_dir / "flow_steps.csv"
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["order", "phase", "step_name", "action", "selector_ref", "param", "enabled"])
            w.writerow([1, "per_tag", "on", "click", "search_icon", "", "TRUE"])
            w.writerow([2, "per_tag", "off", "wait", "", "step1", "no"])
        loaded = storage.load_flow_steps()
        assert loaded[0]["enabled"] is True
        assert loaded[1]["enabled"] is False

    def test_corrupted_file_returns_defaults(self, tmp_data_dir):
        (tmp_data_dir / "flow_steps.csv").write_bytes(b"\xff\xfe not csv")
        assert storage.load_flow_steps() == storage.flow_steps_defaults()


# ── folder-based config sharing ─────────────────────────────────────────────────

class TestConfigShare:
    def test_export_writes_known_files(self, tmp_path):
        dest = tmp_path / "out"
        written = storage.export_config_to_dir(dest)
        # write-on-load files are materialized + copied
        for name in ("settings.csv", "web.csv", "delays.csv", "flow.csv",
                     "flow_steps.csv", "selectors.csv", "target.csv"):
            assert name in written
            assert (dest / name).exists()

    def test_export_skips_excluded_when_absent(self, tmp_path):
        written = storage.export_config_to_dir(tmp_path / "out")
        assert "excluded.csv" not in written

    def test_export_then_import_roundtrip(self, tmp_path, tmp_data_dir):
        # Change a value, export, mutate the live data, then import to restore.
        storage.save_target({"min_followers": 1234, "max_followers": 0,
                             "min_following": 0, "max_following": 0,
                             "min_posts": 0, "keyword": "", "mode": "hashtag"})
        dest = tmp_path / "shared"
        storage.export_config_to_dir(dest)

        storage.save_target({"min_followers": 9999, "max_followers": 0,
                             "min_following": 0, "max_following": 0,
                             "min_posts": 0, "keyword": "", "mode": "hashtag"})
        assert storage.load_target()["min_followers"] == 9999

        imported = storage.import_config_from_dir(dest)
        assert "target.csv" in imported
        assert storage.load_target()["min_followers"] == 1234

    def test_import_only_present_files(self, tmp_path, tmp_data_dir):
        src = tmp_path / "partial"
        src.mkdir()
        storage.save_flow_steps(storage.flow_steps_defaults())
        # Put only flow_steps.csv in the import folder.
        import shutil
        shutil.copy2(tmp_data_dir / "flow_steps.csv", src / "flow_steps.csv")
        imported = storage.import_config_from_dir(src)
        assert imported == ["flow_steps.csv"]

    def test_import_skips_non_csv(self, tmp_path, tmp_data_dir):
        src = tmp_path / "bad"
        src.mkdir()
        (src / "web.csv").write_bytes(b"\xff\xfe\x00\x01 binary")
        imported = storage.import_config_from_dir(src)
        assert "web.csv" not in imported
