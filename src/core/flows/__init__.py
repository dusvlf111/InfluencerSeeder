"""Flow registry — maps a collection ``mode`` string to a ``Flow`` subclass.

Add a new collection strategy with two lines::

    from core.flows.base import Flow
    from core.flows import register

    class MyFlow(Flow):
        mode = "myflow"
        def run(self, ctx): ...

    register("myflow", MyFlow)

``get_flow(mode)`` returns a fresh instance; unknown modes fall back to the
default ``"hashtag"`` flow (with a logged warning).
"""

import logging

from core.flows.base import Outcome, Step, Flow
from core.flows.context import ScrapeContext

_log = logging.getLogger(__name__)

_DEFAULT_MODE = "hashtag"
_REGISTRY: dict[str, type] = {}


def register(mode: str, cls: type) -> None:
    """Register ``cls`` (a Flow subclass) under ``mode``."""
    _REGISTRY[mode] = cls


def get_flow(mode: str) -> Flow:
    """Return a Flow instance for ``mode``, falling back to ``hashtag``."""
    cls = _REGISTRY.get(mode)
    if cls is None:
        _log.warning(
            "no flow registered for mode %r; falling back to %r",
            mode, _DEFAULT_MODE,
        )
        cls = _REGISTRY[_DEFAULT_MODE]
    return cls()


__all__ = [
    "Outcome", "Step", "Flow", "ScrapeContext",
    "register", "get_flow",
]


# ── Default registrations ──────────────────────────────────────────────────────
from core.flows.hashtag import HashtagFlow            # noqa: E402
from core.flows.configurable import ConfigurableFlow  # noqa: E402

# The default "hashtag"/"keyword" modes now run the data-driven ConfigurableFlow,
# which interprets flow_steps.csv and falls back to HashtagFlow when that file is
# empty/invalid. The original hard-coded flow stays available as a regression /
# fallback baseline under "hashtag_legacy".
register("hashtag", ConfigurableFlow)
register("keyword", ConfigurableFlow)   # alias — keyword mode reuses the hashtag flow
register("hashtag_legacy", HashtagFlow)
