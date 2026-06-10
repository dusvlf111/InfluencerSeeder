import json
import pytest
from pathlib import Path
from unittest.mock import patch

import core.storage as storage


@pytest.fixture(autouse=True)
def tmp_data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "DATA_DIR", tmp_path)
    yield tmp_path


class TestExcluded:
    def test_load_returns_empty_when_no_file(self):
        assert storage.load_excluded() == []

    def test_save_and_load_roundtrip(self):
        accounts = ["user_a", "user_b", "user_c"]
        storage.save_excluded(accounts)
        loaded = storage.load_excluded()
        assert sorted(loaded) == sorted(accounts)

    def test_save_deduplicates(self):
        storage.save_excluded(["alice", "alice", "bob"])
        loaded = storage.load_excluded()
        assert loaded.count("alice") == 1

    def test_save_sorts(self):
        storage.save_excluded(["zzz", "aaa", "mmm"])
        loaded = storage.load_excluded()
        assert loaded == ["aaa", "mmm", "zzz"]

    def test_load_corrupted_json_returns_empty(self, tmp_path):
        (tmp_path / "excluded.json").write_text("not json", encoding="utf-8")
        assert storage.load_excluded() == []


class TestSettings:
    def test_load_returns_defaults_when_no_file(self):
        s = storage.load_settings()
        assert s["min_followers"] == 0
        assert s["max_followers"] == 0
        assert s["max_scroll"] == 15
        assert s["sel_tab_recent"] != ""

    def test_save_and_load_roundtrip(self):
        data = {
            "min_followers": 1000,
            "max_followers": 50000,
            "max_scroll": 20,
        }
        storage.save_settings(data)
        loaded = storage.load_settings()
        assert loaded["min_followers"] == 1000
        assert loaded["max_followers"] == 50000
        assert loaded["max_scroll"] == 20

    def test_load_merges_missing_keys_with_defaults(self, tmp_path):
        (tmp_path / "settings.json").write_text(
            json.dumps({"min_followers": 500}), encoding="utf-8"
        )
        s = storage.load_settings()
        assert s["min_followers"] == 500
        assert s["max_followers"] == 0  # default

    def test_load_corrupted_json_returns_defaults(self, tmp_path):
        (tmp_path / "settings.json").write_text("{bad json", encoding="utf-8")
        s = storage.load_settings()
        assert s["min_followers"] == 0
