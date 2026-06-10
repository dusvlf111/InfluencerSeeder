"""Core abstractions for pluggable scrape flows.

A ``Flow`` orchestrates a collection ``mode`` (e.g. ``hashtag``) by running an
ordered sequence of ``Step`` objects against a ``ScrapeContext``. Each Step
returns an ``Outcome`` that tells the Flow how to proceed (continue, skip the
current post, move to the next tag, abort on block, or stop entirely).

Steps and Flows never touch UI widgets directly — they communicate through
``ctx.thread.<signal>.emit(...)`` only (see CLAUDE.md §1).
"""

from abc import ABC, abstractmethod
from enum import Enum, auto


class Outcome(Enum):
    CONTINUE = auto()   # proceed to the next step
    SKIP_POST = auto()  # skip the current post, continue the post loop
    NEXT_TAG = auto()   # end the current tag loop early
    BLOCKED = auto()    # block/challenge detected — abort everything
    STOP = auto()       # user stop / collection target reached


class Step(ABC):
    """A single unit of work against the current ScrapeContext."""

    @abstractmethod
    def execute(self, ctx) -> "Outcome":
        ...


class Flow(ABC):
    """Orchestrates a full collection run for one ``mode``."""

    mode: str = "base"

    @abstractmethod
    def run(self, ctx) -> None:
        ...
