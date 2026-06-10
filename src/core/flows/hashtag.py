"""Hashtag collection flow.

Drives Instagram's tag search → grid → post → profile pipeline using the
reusable Steps in ``core.flows.steps`` and the capability methods on
``ctx.thread`` (ScraperThread). The full orchestration is filled in at R1.5;
this module also serves as the default registered flow (and the ``keyword``
alias) from R1.3 onward.
"""

from core.flows.base import Flow


class HashtagFlow(Flow):
    mode = "hashtag"

    def run(self, ctx) -> None:  # pragma: no cover - replaced at R1.5
        raise NotImplementedError("HashtagFlow.run is implemented in R1.5")
