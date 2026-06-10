"""Persistent run-log file (§8).

Writes a per-run log file under ``storage.DATA_DIR / "logs"`` named
``run-YYYYMMDD-HHMMSS.log``. Each line is::

    [ISO8601] [LEVEL] [step_id] message

File IO is funneled here (the only place that opens the log file), and the
directory is resolved dynamically from ``storage.DATA_DIR`` so the
``monkeypatch.setattr(storage, "DATA_DIR", tmp_path)`` test contract holds —
the path is never cached at import time.
"""

import datetime
from pathlib import Path


def _logs_dir() -> Path:
    """Resolve the logs directory against the (monkeypatchable) DATA_DIR."""
    from core import storage
    return Path(storage.DATA_DIR) / "logs"


class RunLogger:
    """Append-only log file for a single scrape run.

    Created when a scrape starts; ``write()`` records one line per event and
    flushes immediately so a crash still leaves a complete tail. ``close()``
    is idempotent.
    """

    def __init__(self):
        logs = _logs_dir()
        logs.mkdir(parents=True, exist_ok=True)
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        self.path = logs / f"run-{stamp}.log"
        self._file = open(self.path, "a", encoding="utf-8")

    def write(self, level: str, step_id: str, message: str):
        """Record one ``[ISO8601] [LEVEL] [step_id] message`` line + flush.

        No-op after ``close()``.
        """
        if self._file is None:
            return
        ts = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
        lvl = (level or "INFO").upper()
        sid = step_id or "-"
        line = f"[{ts}] [{lvl}] [{sid}] {message}\n"
        try:
            self._file.write(line)
            self._file.flush()
        except Exception:
            pass

    def close(self):
        if self._file is not None:
            try:
                self._file.close()
            finally:
                self._file = None
