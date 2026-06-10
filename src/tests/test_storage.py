import json
import pytest

import core.storage as storage


@pytest.fixture(autouse=True)
def tmp_data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "DATA_DIR", tmp_path)
    yield tmp_path


# ── Settings (v2 — 마이그레이션 호환) ───────────────────────────────────────────
# NOTE: 기존 stale 테스트(max_scroll/sel_tab_recent/settings.json/excluded.json)는
# 현행 storage.py 스키마(settings.csv, key,value)에 맞춰 갱신함.

class TestSettings:
    def test_load_returns_defaults_when_no_file(self):
        s = storage.load_settings()
        assert s["min_followers"] == 0
        assert s["max_followers"] == 0
        assert s["posts_per_tag"] == 5
        assert s["max_tags"] == 3

    def test_load_creates_file(self, tmp_data_dir):
        storage.load_settings()
        assert (tmp_data_dir / "settings.csv").exists()

    def test_save_and_load_roundtrip(self):
        storage.save_settings({"min_followers": 1000, "max_followers": 50000, "max_tags": 6})
        loaded = storage.load_settings()
        assert loaded["min_followers"] == 1000
        assert loaded["max_followers"] == 50000
        assert loaded["max_tags"] == 6

    def test_load_merges_missing_keys_with_defaults(self):
        storage.save_settings({"min_followers": 500})
        s = storage.load_settings()
        assert s["min_followers"] == 500
        assert s["max_followers"] == 0  # default

    def test_load_corrupted_file_returns_defaults(self, tmp_data_dir):
        (tmp_data_dir / "settings.csv").write_bytes(b"\xff\xfe not csv")
        s = storage.load_settings()
        assert s["min_followers"] == 0


class TestExcluded:
    def test_load_returns_empty_when_no_file(self):
        assert storage.load_excluded() == []

    def test_save_and_load_roundtrip(self):
        accounts = ["user_a", "user_b", "user_c"]
        storage.save_excluded(accounts)
        assert sorted(storage.load_excluded()) == sorted(accounts)

    def test_save_deduplicates(self):
        storage.save_excluded(["alice", "alice", "bob"])
        assert storage.load_excluded().count("alice") == 1

    def test_save_sorts(self):
        storage.save_excluded(["zzz", "aaa", "mmm"])
        assert storage.load_excluded() == ["aaa", "mmm", "zzz"]

    def test_load_corrupted_file_returns_empty(self, tmp_data_dir):
        (tmp_data_dir / "excluded.csv").write_bytes(b"\xff\xfe broken")
        assert storage.load_excluded() == []


# ── 1.1 Web settings ───────────────────────────────────────────────────────────

class TestWeb:
    def test_load_returns_defaults_when_no_file(self):
        w = storage.load_web()
        assert w["browser"] == "chrome"
        assert w["headless"] == "false"
        assert w["window_width"] == 1280
        assert w["window_height"] == 900
        assert w["randomize_window"] == "true"
        assert w["locale"] == "ko-KR"
        assert w["implicit_wait"] == 5
        assert w["page_load_timeout"] == 30

    def test_load_creates_file(self, tmp_data_dir):
        storage.load_web()
        assert (tmp_data_dir / "web.csv").exists()

    def test_web_defaults_helper(self):
        d = storage.web_defaults()
        assert d["browser"] == "chrome"
        assert str(d["headless"]).lower() == "false"
        assert str(d["randomize_user_agent"]).lower() == "true"

    def test_save_and_load_roundtrip(self):
        storage.save_web({
            "browser": "chrome", "headless": "true", "window_width": 1440,
            "window_height": 900, "randomize_window": "false",
            "randomize_user_agent": "false", "user_data_dir": "/tmp/p",
            "locale": "en-US", "implicit_wait": 8, "page_load_timeout": 60,
        })
        w = storage.load_web()
        assert w["headless"] == "true"
        assert w["window_width"] == 1440
        assert w["user_data_dir"] == "/tmp/p"
        assert w["locale"] == "en-US"
        assert w["implicit_wait"] == 8

    def test_load_merges_missing_keys(self):
        storage.save_web({"headless": "true"})
        w = storage.load_web()
        assert w["headless"] == "true"
        assert w["browser"] == "chrome"  # default merged

    def test_load_corrupted_file_returns_defaults(self, tmp_data_dir):
        (tmp_data_dir / "web.csv").write_bytes(b"\xff\xfe broken")
        w = storage.load_web()
        assert w["browser"] == "chrome"


# ── 1.2 Selectors with priority ────────────────────────────────────────────────

class TestSelectors:
    def test_load_returns_defaults_when_no_file(self):
        rows = storage.load_selectors()
        step_ids = {r["step_id"] for r in rows}
        for sid in ("search_icon", "search_input", "tag_result", "post_link",
                    "profile_link", "username_text", "followers_count",
                    "following_count", "posts_count", "bio_text", "website_link"):
            assert sid in step_ids

    def test_load_creates_file(self, tmp_data_dir):
        storage.load_selectors()
        assert (tmp_data_dir / "selectors.csv").exists()

    def test_default_rows_have_priority_field(self):
        for r in storage.load_selectors():
            assert "priority" in r
            assert isinstance(r["priority"], int)

    def test_priority_sorted_ascending_per_step(self):
        rows = storage.load_selectors()
        search_icon = [r for r in rows if r["step_id"] == "search_icon"]
        prios = [r["priority"] for r in search_icon]
        assert prios == sorted(prios)
        assert prios == [1, 2, 3]

    def test_roundtrip_with_new_fields(self):
        storage.save_selectors([
            {"step_id": "search_icon", "step_name": "A", "priority": 2,
             "selector_type": "css", "selector_value": "div.b"},
            {"step_id": "search_icon", "step_name": "A", "priority": 1,
             "selector_type": "css", "selector_value": "div.a"},
        ])
        rows = storage.load_selectors()
        assert [r["priority"] for r in rows] == [1, 2]
        assert rows[0]["selector_value"] == "div.a"

    def test_missing_priority_defaults_to_one(self, tmp_data_dir):
        path = tmp_data_dir / "selectors.csv"
        path.write_text(
            "step_id,step_name,priority,selector_type,selector_value\n"
            "search_icon,A,,xpath,//a\n",
            encoding="utf-8-sig",
        )
        rows = storage.load_selectors()
        assert rows[0]["priority"] == 1

    def test_coord_selector_allowed(self):
        storage.save_selectors([
            {"step_id": "search_icon", "step_name": "A", "priority": 9,
             "selector_type": "coord", "selector_value": "120,340"},
        ])
        rows = storage.load_selectors()
        assert rows[0]["selector_type"] == "coord"
        assert rows[0]["selector_value"] == "120,340"

    def test_load_corrupted_file_returns_defaults(self, tmp_data_dir):
        (tmp_data_dir / "selectors.csv").write_bytes(b"\xff\xfe broken")
        rows = storage.load_selectors()
        assert any(r["step_id"] == "search_icon" for r in rows)


# ── 1.3 Delays ─────────────────────────────────────────────────────────────────

class TestDelays:
    def test_load_returns_defaults_when_no_file(self):
        d = storage.load_delays()
        assert d["step1"] == (1.0, 2.5)
        assert d["typing_char"] == (0.05, 0.18)
        assert d["scroll"] == (0.8, 2.0)

    def test_load_creates_file(self, tmp_data_dir):
        storage.load_delays()
        assert (tmp_data_dir / "delays.csv").exists()

    def test_values_are_tuples_of_floats(self):
        d = storage.load_delays()
        for k, v in d.items():
            assert isinstance(v, tuple) and len(v) == 2
            assert isinstance(v[0], float) and isinstance(v[1], float)

    def test_save_and_load_roundtrip(self):
        storage.save_delays({"step1": (3.0, 5.0), "back": (0.2, 0.4)})
        d = storage.load_delays()
        assert d["step1"] == (3.0, 5.0)
        assert d["back"] == (0.2, 0.4)

    def test_load_merges_missing_keys(self):
        storage.save_delays({"step1": (9.0, 9.0)})
        d = storage.load_delays()
        assert d["step1"] == (9.0, 9.0)
        assert d["typing_char"] == (0.05, 0.18)  # default merged

    def test_load_corrupted_file_returns_defaults(self, tmp_data_dir):
        (tmp_data_dir / "delays.csv").write_bytes(b"\xff\xfe broken")
        d = storage.load_delays()
        assert d["step1"] == (1.0, 2.5)


# ── 1.4 Flow ───────────────────────────────────────────────────────────────────

class TestFlow:
    def test_load_returns_defaults_when_no_file(self):
        f = storage.load_flow()
        assert f["max_tags"] == 3
        assert f["tag_start_index"] == 0
        assert f["posts_per_tag"] == 5
        assert f["scroll_max_attempts"] == 15
        assert f["skip_visited_profile"] == "true"
        assert f["stop_on_consecutive_miss"] == 10

    def test_load_creates_file(self, tmp_data_dir):
        storage.load_flow()
        assert (tmp_data_dir / "flow.csv").exists()

    def test_save_and_load_roundtrip(self):
        storage.save_flow({"max_tags": 7, "posts_per_tag": 12, "skip_visited_profile": "false"})
        f = storage.load_flow()
        assert f["max_tags"] == 7
        assert f["posts_per_tag"] == 12
        assert f["skip_visited_profile"] == "false"

    def test_load_merges_missing_keys(self):
        storage.save_flow({"max_tags": 99})
        f = storage.load_flow()
        assert f["max_tags"] == 99
        assert f["posts_per_tag"] == 5  # default

    def test_load_corrupted_file_returns_defaults(self, tmp_data_dir):
        (tmp_data_dir / "flow.csv").write_bytes(b"\xff\xfe broken")
        f = storage.load_flow()
        assert f["max_tags"] == 3


# ── 1.5 Target ─────────────────────────────────────────────────────────────────

class TestTarget:
    def test_load_returns_defaults_when_no_file(self):
        t = storage.load_target()
        assert t["min_followers"] == 0
        assert t["max_followers"] == 0
        assert t["min_following"] == 0
        assert t["max_following"] == 0
        assert t["min_posts"] == 0
        assert t["keyword"] == ""
        assert t["mode"] == "hashtag"

    def test_load_creates_file(self, tmp_data_dir):
        storage.load_target()
        assert (tmp_data_dir / "target.csv").exists()

    def test_save_and_load_roundtrip(self):
        storage.save_target({"min_followers": 5000, "max_followers": 100000,
                             "keyword": "인턴", "mode": "hashtag"})
        t = storage.load_target()
        assert t["min_followers"] == 5000
        assert t["max_followers"] == 100000
        assert t["keyword"] == "인턴"

    def test_load_merges_missing_keys(self):
        storage.save_target({"min_posts": 50})
        t = storage.load_target()
        assert t["min_posts"] == 50
        assert t["mode"] == "hashtag"  # default

    def test_load_corrupted_file_returns_defaults(self, tmp_data_dir):
        (tmp_data_dir / "target.csv").write_bytes(b"\xff\xfe broken")
        t = storage.load_target()
        assert t["mode"] == "hashtag"


# ── 1.6 Results dedup ──────────────────────────────────────────────────────────

class TestResultsDedup:
    def _info(self, username, **kw):
        base = {"username": username, "full_name": "Name", "followers": 1000,
                "following": 100, "posts_count": 50, "bio": "hi",
                "website": "", "is_private": "false", "profile_url": "u",
                "source_tag": "tag", "source_post_url": "p", "collected_at": "now"}
        base.update(kw)
        return base

    def test_append_new_returns_true_and_writes(self, tmp_data_dir):
        assert storage.append_result(self._info("Alice")) is True
        rows = storage.load_results()
        assert len(rows) == 1
        assert rows[0]["username"] == "alice"  # lower-cased
        assert rows[0]["full_name"] == "Name"

    def test_duplicate_case_insensitive_returns_false(self):
        assert storage.append_result(self._info("Alice")) is True
        assert storage.append_result(self._info("alice")) is False
        assert storage.append_result(self._info("ALICE")) is False
        assert len(storage.load_results()) == 1

    def test_excluded_username_not_appended(self):
        storage.save_excluded(["BlockedUser"])
        assert storage.append_result(self._info("blockeduser")) is False
        assert storage.load_results() == []

    def test_empty_username_returns_false(self):
        assert storage.append_result(self._info("")) is False
        assert storage.append_result({"full_name": "x"}) is False

    def test_seen_usernames_union_lowercased(self):
        storage.append_result(self._info("Alice"))
        storage.append_result(self._info("Bob"))
        storage.save_excluded(["Carol", "dave"])
        seen = storage.seen_usernames()
        assert seen == {"alice", "bob", "carol", "dave"}

    def test_seen_usernames_empty_when_nothing(self):
        assert storage.seen_usernames() == set()


# ── 1.7 State ──────────────────────────────────────────────────────────────────

class TestState:
    def _state(self):
        return {
            "keyword": "인턴", "tag_index": 1, "post_index": 3,
            "collected_count": 17, "seen_usernames": ["abc", "def"],
            "updated_at": "2026-06-10T13:20:00+09:00",
        }

    def test_load_returns_none_when_no_file(self):
        assert storage.load_state() is None

    def test_save_and_load_roundtrip(self):
        storage.save_state(self._state())
        s = storage.load_state()
        assert s["keyword"] == "인턴"
        assert s["tag_index"] == 1
        assert s["seen_usernames"] == ["abc", "def"]

    def test_save_creates_file(self, tmp_data_dir):
        storage.save_state(self._state())
        assert (tmp_data_dir / "state.json").exists()

    def test_clear_removes_file(self, tmp_data_dir):
        storage.save_state(self._state())
        storage.clear_state()
        assert not (tmp_data_dir / "state.json").exists()
        assert storage.load_state() is None

    def test_clear_when_no_file_is_safe(self):
        storage.clear_state()  # must not raise
        assert storage.load_state() is None

    def test_load_corrupted_json_returns_none(self, tmp_data_dir):
        (tmp_data_dir / "state.json").write_text("{bad json", encoding="utf-8")
        assert storage.load_state() is None

    def test_non_dict_json_returns_none(self, tmp_data_dir):
        (tmp_data_dir / "state.json").write_text(json.dumps([1, 2, 3]), encoding="utf-8")
        assert storage.load_state() is None
