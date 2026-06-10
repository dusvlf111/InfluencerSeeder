"""Mutable per-run context passed to every Step/Flow.

Holds the live Selenium ``driver``, the owning ``ScraperThread`` (the source of
all "capability" methods and signals), plus per-run loop state. Convenience
properties delegate to the thread so Steps don't reach into private attrs.
"""

from dataclasses import dataclass, field


@dataclass
class ScrapeContext:
    thread: object                 # ScraperThread — capability methods + signals
    driver: object                 # Selenium WebDriver (or MagicMock in tests)
    keyword: str = ""
    tag_grid_url: str = ""
    post_urls: list = field(default_factory=list)
    # Current loop indices (set by the Flow as it iterates).
    tag_index: int = 0
    post_index: int = 0

    # ── Delegating conveniences ────────────────────────────────────────────────

    @property
    def collected(self) -> int:
        return getattr(self.thread, "_collected", 0)

    @collected.setter
    def collected(self, value: int) -> None:
        self.thread._collected = int(value)

    @property
    def count(self) -> int:
        return getattr(self.thread, "count", 0)

    @property
    def stop_requested(self) -> bool:
        return bool(getattr(self.thread, "_stop", False))
