import pytest
from unittest.mock import MagicMock, patch

from core.flows import get_flow, register, Outcome, Step, Flow
from core.flows.context import ScrapeContext
from core.flows.hashtag import HashtagFlow
from core.flows.configurable import ConfigurableFlow
from core.scraper import ScraperThread


class TestFlowRegistry:
    def test_get_flow_hashtag_returns_configurable_flow(self):
        # 260610-4: the default hashtag mode is now the data-driven ConfigurableFlow.
        flow = get_flow("hashtag")
        assert isinstance(flow, ConfigurableFlow)
        assert flow.mode == "hashtag"

    def test_keyword_alias_maps_to_configurable_flow(self):
        flow = get_flow("keyword")
        assert isinstance(flow, ConfigurableFlow)

    def test_hashtag_legacy_maps_to_hashtagflow(self):
        flow = get_flow("hashtag_legacy")
        assert isinstance(flow, HashtagFlow)

    def test_unknown_mode_falls_back_to_hashtag(self):
        flow = get_flow("does-not-exist")
        assert isinstance(flow, ConfigurableFlow)

    def test_get_flow_returns_fresh_instances(self):
        assert get_flow("hashtag") is not get_flow("hashtag")

    def test_register_custom_flow(self):
        class _DummyFlow(Flow):
            mode = "dummy"

            def run(self, ctx):
                return None

        register("dummy-test", _DummyFlow)
        try:
            assert isinstance(get_flow("dummy-test"), _DummyFlow)
        finally:
            from core.flows import _REGISTRY
            _REGISTRY.pop("dummy-test", None)

    def test_step_is_abstract(self):
        with pytest.raises(TypeError):
            Step()

    def test_flow_is_abstract(self):
        with pytest.raises(TypeError):
            Flow()

    def test_outcome_members(self):
        names = {o.name for o in Outcome}
        assert names == {"CONTINUE", "SKIP_POST", "NEXT_TAG", "BLOCKED", "STOP"}


def _make_thread(**over):
    """Build a ScraperThread shell (no __init__) with the capability methods and
    attributes the flow touches. Selenium-driven internals are stubbed; dedup,
    filter, save, and signal logic stay real."""
    t = ScraperThread.__new__(ScraperThread)
    t.search_term = "인턴"
    t.count = 10
    t.min_followers = 0
    t.max_followers = 0
    t.posts_per_tag = 5
    t.max_tags = 1
    t._collected = 0
    t._stop = False
    t._start_tag_index = 0
    t._start_post_index = 0
    t._seen = set()
    t._blocked = False
    # Signals → MagicMock so we can assert emit() calls without a Qt loop.
    for sig in ("result_signal", "progress_signal", "skip_signal", "blocked_signal"):
        setattr(t, sig, MagicMock())
    # Cheap capability methods (no Selenium): keep real behavior where harmless.
    t._log = lambda msg: None
    t._step = lambda msg: None
    t._random_delay = lambda key: None
    t._save_state = lambda tag, post: None
    t._is_blocked = lambda driver: False
    for k, v in over.items():
        setattr(t, k, v)
    return t


class TestHashtagFlowSmoke:
    """Network-free smoke tests for HashtagFlow.run() — all Selenium-heavy steps
    are patched at the flow's step-class seams; storage is patched."""

    def _patch_steps(self, post_urls, profile_info):
        """Patch the Selenium-driven steps so the flow exercises only its
        orchestration + the real dedup/filter/save path."""
        from core.flows import hashtag as hf

        def _collect(self, ctx):
            ctx.post_urls = list(post_urls)
            return Outcome.CONTINUE

        def _peek(self, ctx):
            # Mirror real gate: dedup against thread._should_skip on username.
            uname = profile_info.get("username", "")
            if uname and ctx.thread._should_skip(uname):
                return Outcome.SKIP_POST
            return Outcome.CONTINUE

        def _nav(self, ctx):
            ctx.profile_url = f"https://www.instagram.com/{profile_info['username']}/"
            return Outcome.CONTINUE

        def _extract(self, ctx):
            ctx.profile_info = dict(profile_info)
            return Outcome.CONTINUE

        return [
            patch.object(hf, "ClickSearchIcon", lambda: MagicMock(execute=lambda ctx: Outcome.CONTINUE)),
            patch.object(hf, "TypeSearch", lambda: MagicMock(execute=lambda ctx: Outcome.CONTINUE)),
            patch.object(hf, "ClickTagSuggestion", lambda: MagicMock(execute=lambda ctx: Outcome.CONTINUE)),
            patch.object(hf.CollectPostUrls, "execute", _collect),
            patch.object(hf.PeekUsernameGate, "execute", _peek),
            patch.object(hf.NavigateToProfile, "execute", _nav),
            patch.object(hf.ExtractProfile, "execute", _extract),
        ]

    def test_zero_posts_finishes_without_save(self):
        t = _make_thread()
        driver = MagicMock()
        driver.current_url = "https://www.instagram.com/explore/tags/intern/"
        ctx = ScrapeContext(thread=t, driver=driver)
        patches = self._patch_steps(post_urls=[], profile_info={"username": "x"})
        with patch("core.storage.append_result") as appended:
            for p in patches:
                p.start()
            try:
                HashtagFlow().run(ctx)
            finally:
                for p in patches:
                    p.stop()
        appended.assert_not_called()
        t.result_signal.emit.assert_not_called()

    def test_single_valid_profile_saved(self):
        t = _make_thread()
        driver = MagicMock()
        driver.current_url = "https://www.instagram.com/explore/tags/intern/"
        ctx = ScrapeContext(thread=t, driver=driver)
        info = {"username": "newuser", "followers": "5천"}
        patches = self._patch_steps(post_urls=["https://www.instagram.com/p/abc/"], profile_info=info)
        with patch("core.storage.append_result", return_value=True) as appended:
            for p in patches:
                p.start()
            try:
                HashtagFlow().run(ctx)
            finally:
                for p in patches:
                    p.stop()
        appended.assert_called_once()
        saved = appended.call_args[0][0]
        assert saved["username"] == "newuser"
        assert saved["source_tag"] == "인턴"
        assert saved["source_post_url"] == "https://www.instagram.com/p/abc/"
        t.result_signal.emit.assert_called_once()
        assert t._collected == 1

    def test_duplicate_profile_skipped(self):
        t = _make_thread()
        t._seen = {"dupuser"}
        driver = MagicMock()
        driver.current_url = "https://www.instagram.com/explore/tags/intern/"
        ctx = ScrapeContext(thread=t, driver=driver)
        info = {"username": "dupuser", "followers": "5천"}
        patches = self._patch_steps(post_urls=["https://www.instagram.com/p/abc/"], profile_info=info)
        with patch("core.storage.append_result", return_value=True) as appended:
            for p in patches:
                p.start()
            try:
                HashtagFlow().run(ctx)
            finally:
                for p in patches:
                    p.stop()
        appended.assert_not_called()
        t.skip_signal.emit.assert_called_with("dupuser")
        assert t._collected == 0

    def test_follower_filter_miss_skipped(self):
        t = _make_thread(min_followers=10_000)
        driver = MagicMock()
        driver.current_url = "https://www.instagram.com/explore/tags/intern/"
        ctx = ScrapeContext(thread=t, driver=driver)
        info = {"username": "smallacct", "followers": "5천"}  # 5000 < 10000
        patches = self._patch_steps(post_urls=["https://www.instagram.com/p/abc/"], profile_info=info)
        with patch("core.storage.append_result", return_value=True) as appended:
            for p in patches:
                p.start()
            try:
                HashtagFlow().run(ctx)
            finally:
                for p in patches:
                    p.stop()
        appended.assert_not_called()
        assert "smallacct" in t._seen
        assert t._collected == 0


# ── ConfigurableFlow (data-driven) ──────────────────────────────────────────────

import core.storage as storage  # noqa: E402


@pytest.fixture
def tmp_data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "DATA_DIR", tmp_path)
    return tmp_path


def _patch_config_steps(post_urls, profile_info):
    """Patch the Selenium-driven Steps at their class seams (shared by
    ConfigurableFlow and HashtagFlow) so the flow exercises only its
    orchestration + the real dedup/filter/save path."""
    from core.flows import steps as st

    def _click(self, ctx):
        return Outcome.CONTINUE

    def _type(self, ctx):
        return Outcome.CONTINUE

    def _click_idx(self, ctx):
        return Outcome.CONTINUE

    def _collect(self, ctx):
        ctx.post_urls = list(post_urls)
        return Outcome.CONTINUE

    def _peek(self, ctx):
        uname = profile_info.get("username", "")
        if uname and ctx.thread._should_skip(uname):
            return Outcome.SKIP_POST
        return Outcome.CONTINUE

    def _nav(self, ctx):
        ctx.profile_url = f"https://www.instagram.com/{profile_info['username']}/"
        return Outcome.CONTINUE

    def _extract(self, ctx):
        ctx.profile_info = dict(profile_info)
        return Outcome.CONTINUE

    return [
        patch.object(st.ClickStep, "execute", _click),
        patch.object(st.TypeStep, "execute", _type),
        patch.object(st.ClickIndexStep, "execute", _click_idx),
        patch.object(st.CollectPostUrls, "execute", _collect),
        patch.object(st.PeekUsernameGate, "execute", _peek),
        patch.object(st.NavigateToProfile, "execute", _nav),
        patch.object(st.ExtractProfile, "execute", _extract),
    ]


def _run_configurable(ctx, post_urls, profile_info, append_return=True):
    from core.flows.configurable import ConfigurableFlow
    patches = _patch_config_steps(post_urls, profile_info)
    with patch("core.storage.append_result", return_value=append_return) as appended:
        for p in patches:
            p.start()
        try:
            ConfigurableFlow().run(ctx)
        finally:
            for p in patches:
                p.stop()
    return appended


class TestConfigurableFlowDefault:
    """ConfigurableFlow on the DEFAULT flow_steps must match HashtagFlow's
    observable behavior: same append_result calls, signals, _collected, and
    back-navigation. Storage is patched (tmp DATA_DIR + append_result)."""

    def _driver(self):
        d = MagicMock()
        d.current_url = "https://www.instagram.com/explore/tags/intern/"
        return d

    def test_single_valid_profile_saved(self, tmp_data_dir):
        t = _make_thread()
        driver = self._driver()
        ctx = ScrapeContext(thread=t, driver=driver)
        info = {"username": "newuser", "followers": "5천"}
        appended = _run_configurable(ctx, ["https://www.instagram.com/p/abc/"], info)
        appended.assert_called_once()
        saved = appended.call_args[0][0]
        assert saved["username"] == "newuser"
        assert saved["source_tag"] == "인턴"
        assert saved["source_post_url"] == "https://www.instagram.com/p/abc/"
        t.result_signal.emit.assert_called_once()
        assert t._collected == 1

    def test_zero_posts_no_save(self, tmp_data_dir):
        t = _make_thread()
        ctx = ScrapeContext(thread=t, driver=self._driver())
        appended = _run_configurable(ctx, [], {"username": "x"})
        appended.assert_not_called()
        t.result_signal.emit.assert_not_called()

    def test_duplicate_profile_skipped(self, tmp_data_dir):
        t = _make_thread()
        t._seen = {"dupuser"}
        ctx = ScrapeContext(thread=t, driver=self._driver())
        info = {"username": "dupuser", "followers": "5천"}
        appended = _run_configurable(ctx, ["https://www.instagram.com/p/abc/"], info)
        appended.assert_not_called()
        t.skip_signal.emit.assert_called_with("dupuser")
        assert t._collected == 0

    def test_follower_filter_miss_marked_seen(self, tmp_data_dir):
        t = _make_thread(min_followers=10_000)
        ctx = ScrapeContext(thread=t, driver=self._driver())
        info = {"username": "smallacct", "followers": "5천"}
        appended = _run_configurable(ctx, ["https://www.instagram.com/p/abc/"], info)
        appended.assert_not_called()
        assert "smallacct" in t._seen
        assert t._collected == 0

    def test_go_back_returns_to_tag_grid(self, tmp_data_dir):
        t = _make_thread()
        driver = self._driver()
        ctx = ScrapeContext(thread=t, driver=driver)
        info = {"username": "newuser", "followers": "5천"}
        _run_configurable(ctx, ["https://www.instagram.com/p/abc/"], info)
        # Default go_back step does driver.get(tag_grid_url) after a save.
        grid = "https://www.instagram.com/explore/tags/intern/"
        assert any(c.args and c.args[0] == grid for c in driver.get.call_args_list)

    def test_blocked_after_tag_click_aborts(self, tmp_data_dir):
        t = _make_thread(_is_blocked=lambda driver: True)
        driver = self._driver()
        ctx = ScrapeContext(thread=t, driver=driver)
        _run_configurable(ctx, ["https://www.instagram.com/p/abc/"],
                          {"username": "x", "followers": "5천"})
        t.blocked_signal.emit.assert_called_once()
        assert t._blocked is True
        assert t._collected == 0


class TestKeywordPlan:
    """parse_keywords / keyword_tag_plan (Fix-1 A.1)."""

    def test_comma_split(self):
        from core.flows.steps import parse_keywords
        assert parse_keywords("인턴,취준생,개발자") == ["인턴", "취준생", "개발자"]

    def test_newline_split(self):
        from core.flows.steps import parse_keywords
        assert parse_keywords("인턴\n취준생\n개발자") == ["인턴", "취준생", "개발자"]

    def test_mixed_comma_newline_and_whitespace(self):
        from core.flows.steps import parse_keywords
        assert parse_keywords(" 인턴, 취준생\n 개발자 ") == ["인턴", "취준생", "개발자"]

    def test_hash_stripped(self):
        from core.flows.steps import parse_keywords
        assert parse_keywords("#인턴, #취준생") == ["인턴", "취준생"]

    def test_dedup_case_insensitive_order_preserved(self):
        from core.flows.steps import parse_keywords
        assert parse_keywords("Intern,intern,INTERN,dev") == ["Intern", "dev"]

    def test_empty_and_blank_yields_single_empty(self):
        from core.flows.steps import parse_keywords
        assert parse_keywords("") == [""]
        assert parse_keywords(None) == [""]
        assert parse_keywords("  ,  \n ") == [""]

    def test_single_keyword(self):
        from core.flows.steps import parse_keywords
        assert parse_keywords("인턴") == ["인턴"]

    def test_plan_one_tag_per_keyword_index_zero(self):
        from core.flows.steps import keyword_tag_plan
        plan = keyword_tag_plan("인턴,취준생", max_tags=5)
        assert plan == [("인턴", 0), ("취준생", 0)]

    def test_plan_single_keyword(self):
        from core.flows.steps import keyword_tag_plan
        assert keyword_tag_plan("인턴", max_tags=3) == [("인턴", 0)]


class TestMultiKeywordFlow:
    """Each comma keyword is searched separately (one tag/keyword) and its posts
    are processed in sequence — ``ctx.keyword`` tracks the active keyword."""

    def _driver(self):
        d = MagicMock()
        d.current_url = "https://www.instagram.com/explore/tags/intern/"
        return d

    def test_two_keywords_each_searched_and_saved(self, tmp_data_dir):
        t = _make_thread(search_term="인턴,취준생", count=10, max_tags=1)
        driver = self._driver()
        ctx = ScrapeContext(thread=t, driver=driver)

        seen_keywords = []
        saved_tags = []

        from core.flows import steps as st

        def _click(self, ctx):
            return Outcome.CONTINUE

        def _type(self, ctx):
            return Outcome.CONTINUE

        def _click_idx(self, ctx):
            # record which keyword is active when the tag is selected
            seen_keywords.append(ctx.keyword)
            return Outcome.CONTINUE

        def _collect(self, ctx):
            ctx.post_urls = [f"https://www.instagram.com/p/{ctx.keyword}/"]
            return Outcome.CONTINUE

        def _peek(self, ctx):
            return Outcome.CONTINUE

        def _nav(self, ctx):
            ctx.profile_url = f"https://www.instagram.com/{ctx.keyword}_user/"
            return Outcome.CONTINUE

        def _extract(self, ctx):
            ctx.profile_info = {"username": f"{ctx.keyword}_user", "followers": "5천"}
            return Outcome.CONTINUE

        patches = [
            patch.object(st.ClickStep, "execute", _click),
            patch.object(st.TypeStep, "execute", _type),
            patch.object(st.ClickIndexStep, "execute", _click_idx),
            patch.object(st.CollectPostUrls, "execute", _collect),
            patch.object(st.PeekUsernameGate, "execute", _peek),
            patch.object(st.NavigateToProfile, "execute", _nav),
            patch.object(st.ExtractProfile, "execute", _extract),
        ]

        def _append(info):
            saved_tags.append(info["source_tag"])
            return True

        with patch("core.storage.append_result", side_effect=_append):
            for p in patches:
                p.start()
            try:
                ConfigurableFlow().run(ctx)
            finally:
                for p in patches:
                    p.stop()

        # Both keywords searched in order, one tag each.
        assert seen_keywords == ["인턴", "취준생"]
        # A post from each keyword was saved with the keyword as source_tag.
        assert saved_tags == ["인턴", "취준생"]
        assert t._collected == 2

    def test_single_keyword_one_tag_only(self, tmp_data_dir):
        # max_tags high, but single keyword → exactly one tag (no suggestion cycling).
        t = _make_thread(search_term="인턴", count=10, max_tags=9)
        driver = self._driver()
        ctx = ScrapeContext(thread=t, driver=driver)
        clicks = {"n": 0}

        from core.flows import steps as st

        def _noop(self, ctx):
            return Outcome.CONTINUE

        def _click_idx(self, ctx):
            clicks["n"] += 1
            return Outcome.CONTINUE

        def _collect(self, ctx):
            ctx.post_urls = ["https://www.instagram.com/p/abc/"]
            return Outcome.CONTINUE

        def _nav(self, ctx):
            ctx.profile_url = "https://www.instagram.com/newuser/"
            return Outcome.CONTINUE

        def _extract(self, ctx):
            ctx.profile_info = {"username": "newuser", "followers": "5천"}
            return Outcome.CONTINUE

        patches = [
            patch.object(st.ClickStep, "execute", _noop),
            patch.object(st.TypeStep, "execute", _noop),
            patch.object(st.ClickIndexStep, "execute", _click_idx),
            patch.object(st.CollectPostUrls, "execute", _collect),
            patch.object(st.PeekUsernameGate, "execute", _noop),
            patch.object(st.NavigateToProfile, "execute", _nav),
            patch.object(st.ExtractProfile, "execute", _extract),
        ]

        with patch("core.storage.append_result", return_value=True):
            for p in patches:
                p.start()
            try:
                ConfigurableFlow().run(ctx)
            finally:
                for p in patches:
                    p.stop()
        # Only one tag selected despite max_tags=9.
        assert clicks["n"] == 1


class TestConfigurableFlowEditing:
    """Edited flow_steps: disabled steps skipped, unsupported actions ignored,
    empty/invalid steps fall back to HashtagFlow."""

    def _driver(self):
        d = MagicMock()
        d.current_url = "https://www.instagram.com/explore/tags/intern/"
        return d

    def test_disabled_save_skips_persist(self, tmp_data_dir):
        rows = storage.flow_steps_defaults()
        for r in rows:
            if r["action"] == "save":
                r["enabled"] = False
        storage.save_flow_steps(rows)
        t = _make_thread()
        ctx = ScrapeContext(thread=t, driver=self._driver())
        info = {"username": "newuser", "followers": "5천"}
        appended = _run_configurable(ctx, ["https://www.instagram.com/p/abc/"], info)
        appended.assert_not_called()
        assert t._collected == 0

    def test_unsupported_action_ignored(self, tmp_data_dir):
        # load_flow_steps drops unknown actions; even if one slipped into the
        # plan, _build_plan filters it. Inject via raw CSV to be sure.
        import csv as _csv
        path = tmp_data_dir / "flow_steps.csv"
        rows = storage.flow_steps_defaults()
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            w = _csv.DictWriter(
                f, fieldnames=["order", "phase", "step_name", "action",
                               "selector_ref", "param", "enabled"])
            w.writeheader()
            for r in rows:
                out = dict(r)
                out["enabled"] = "true"
                w.writerow(out)
            w.writerow({"order": 99, "phase": "per_post", "step_name": "bogus",
                        "action": "frobnicate", "selector_ref": "", "param": "",
                        "enabled": "true"})
        t = _make_thread()
        ctx = ScrapeContext(thread=t, driver=self._driver())
        info = {"username": "newuser", "followers": "5천"}
        appended = _run_configurable(ctx, ["https://www.instagram.com/p/abc/"], info)
        # Unknown action ignored; normal save still happens.
        appended.assert_called_once()
        assert t._collected == 1

    def test_empty_flow_steps_falls_back(self, tmp_data_dir):
        # All steps disabled → empty plan → HashtagFlow fallback (still saves).
        rows = storage.flow_steps_defaults()
        for r in rows:
            r["enabled"] = False
        storage.save_flow_steps(rows)
        from core.flows import configurable as cfg
        called = {"n": 0}
        real_run = HashtagFlow.run

        def _spy(self, ctx):
            called["n"] += 1
            return real_run(self, ctx)

        t = _make_thread()
        ctx = ScrapeContext(thread=t, driver=self._driver())
        info = {"username": "newuser", "followers": "5천"}
        with patch.object(cfg.HashtagFlow, "run", _spy):
            _run_configurable(ctx, ["https://www.instagram.com/p/abc/"], info)
        assert called["n"] == 1


class TestExtractProfileSelectorFallback:
    """ExtractProfile augments empty fields via user-configured selectors
    (B). meta/page_source are stubbed empty so the selector chain fills them.
    _resolve_selector is MagicMock'd — no live browser."""

    def _thread(self, resolve_map):
        t = ScraperThread.__new__(ScraperThread)
        t._log = lambda msg: None

        def _resolve(driver, step_id):
            return resolve_map.get(step_id)

        t._resolve_selector = _resolve
        return t

    def _driver_no_meta(self, url="https://www.instagram.com/someuser/"):
        d = MagicMock()
        d.current_url = url
        # meta description + bio/website CSS all raise (nothing found),
        # page_source has no JSON counts.
        d.find_element.side_effect = Exception("not found")
        d.page_source = "<html></html>"
        return d

    def test_followers_filled_from_selector(self):
        from core.flows.steps import ExtractProfile
        el = MagicMock()
        el.get_attribute.return_value = "12,345"   # title attribute
        el.text = "12,345"
        t = self._thread({"followers_count": el})
        driver = self._driver_no_meta()
        ctx = ScrapeContext(thread=t, driver=driver)
        out = ExtractProfile().execute(ctx)
        assert out is Outcome.CONTINUE
        assert ctx.profile_info["followers"] == "12,345"

    def test_multiple_fields_filled(self):
        from core.flows.steps import ExtractProfile

        def _el(title="", text="", href=""):
            m = MagicMock()
            m.text = text

            def _attr(name):
                return {"title": title, "href": href}.get(name, "")

            m.get_attribute.side_effect = _attr
            return m

        resolve_map = {
            "username_text": _el(text="홍길동"),
            "followers_count": _el(title="1,000"),
            "following_count": _el(text="200"),
            "posts_count": _el(text="42"),
            "bio_text": _el(text="안녕하세요 개발자입니다"),
            "website_link": _el(href="https://example.com"),
        }
        t = self._thread(resolve_map)
        driver = self._driver_no_meta()
        ctx = ScrapeContext(thread=t, driver=driver)
        ExtractProfile().execute(ctx)
        info = ctx.profile_info
        assert info["full_name"] == "홍길동"
        assert info["followers"] == "1,000"
        assert info["following"] == "200"
        assert info["posts_count"] == "42"
        assert info["bio"] == "안녕하세요 개발자입니다"
        assert info["website"] == "https://example.com"

    def test_meta_value_not_overwritten_by_selector(self):
        # When meta already provided followers, the selector fallback must NOT
        # overwrite it.
        from core.flows.steps import ExtractProfile
        el = MagicMock()
        el.get_attribute.return_value = "999"
        el.text = "999"
        t = self._thread({"followers_count": el})

        d = MagicMock()
        d.current_url = "https://www.instagram.com/someuser/"
        meta = MagicMock()
        meta.get_attribute.return_value = "5,000 Followers, 10 Following, 3 Posts"

        def _find(by, value):
            if "meta" in str(value):
                return meta
            raise Exception("not found")

        d.find_element.side_effect = _find
        d.page_source = "<html></html>"
        ctx = ScrapeContext(thread=t, driver=d)
        ExtractProfile().execute(ctx)
        assert ctx.profile_info["followers"] == "5,000"

    def test_no_selectors_leaves_fields_empty(self):
        from core.flows.steps import ExtractProfile
        t = self._thread({})   # _resolve_selector returns None for everything
        driver = self._driver_no_meta()
        ctx = ScrapeContext(thread=t, driver=driver)
        out = ExtractProfile().execute(ctx)
        assert out is Outcome.CONTINUE
        # username still set from URL; no followers populated.
        assert ctx.profile_info["username"] == "someuser"
        assert "followers" not in ctx.profile_info
