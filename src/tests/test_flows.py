import pytest
from unittest.mock import MagicMock, patch

from core.flows import get_flow, register, Outcome, Step, Flow
from core.flows.context import ScrapeContext
from core.flows.hashtag import HashtagFlow
from core.scraper import ScraperThread


class TestFlowRegistry:
    def test_get_flow_hashtag_returns_hashtagflow(self):
        flow = get_flow("hashtag")
        assert isinstance(flow, HashtagFlow)
        assert flow.mode == "hashtag"

    def test_keyword_alias_maps_to_hashtagflow(self):
        flow = get_flow("keyword")
        assert isinstance(flow, HashtagFlow)

    def test_unknown_mode_falls_back_to_hashtag(self):
        flow = get_flow("does-not-exist")
        assert isinstance(flow, HashtagFlow)

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
