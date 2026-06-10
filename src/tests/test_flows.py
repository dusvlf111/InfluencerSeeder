import pytest

from core.flows import get_flow, register, Outcome, Step, Flow
from core.flows.hashtag import HashtagFlow


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
