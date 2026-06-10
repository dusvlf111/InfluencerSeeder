"""state.json resume-state IO (§3.3).

Routes all file access through ``core.storage`` primitives so the
``monkeypatch.setattr(storage, "DATA_DIR", tmp_path)`` contract holds.
Imports of the facade happen inside functions to avoid an import-time cycle.
"""

import json
from pathlib import Path


def load_state() -> dict | None:
    """Return resume state dict, or None if missing/corrupt."""
    from core import storage as _st
    path = _st._path("state.json")
    if not path.exists():
        return None
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def save_state(data: dict):
    from core import storage as _st
    path = _st._path("state.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def clear_state():
    from core import storage as _st
    path = _st._path("state.json")
    Path(path).unlink(missing_ok=True)
