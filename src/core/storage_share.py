"""Folder-based config sharing (260610-4).

Export writes each known config CSV into a chosen folder under its standard
filename; import reads whichever standard filenames exist in a chosen folder and
copies them into ``DATA_DIR``. There is no combined/bundled file — a shared
folder is just plain CSVs a user can hand off via Drive/messenger.

All paths route through ``core.storage`` so the
``monkeypatch.setattr(storage, "DATA_DIR", tmp_path)`` contract holds.
"""

import csv
import logging
import shutil
from pathlib import Path

_log = logging.getLogger(__name__)

# Standard config filenames → the loader that materializes the file when missing
# (so export can guarantee a file to copy). ``None`` = copy only if it exists
# (e.g. excluded.csv is not written on load).
_CONFIG_LOADERS: dict[str, str | None] = {
    "settings.csv":   "load_settings",
    "web.csv":        "load_web",
    "delays.csv":     "load_delays",
    "flow.csv":       "load_flow",
    "flow_steps.csv": "load_flow_steps",
    "selectors.csv":  "load_selectors",
    "target.csv":     "load_target",
    "excluded.csv":   None,
}

# Public, stable order for UI checklists and iteration.
CONFIG_FILES: list[str] = list(_CONFIG_LOADERS.keys())


def _looks_like_csv(path: Path) -> bool:
    """Light validation: readable as UTF-8 text with a parseable header row."""
    try:
        with open(path, newline="", encoding="utf-8-sig") as f:
            return next(csv.reader(f), None) is not None
    except Exception:
        return False


def export_config_to_dir(dest_dir, names: list[str] | None = None) -> list[str]:
    """Copy each requested config CSV into ``dest_dir`` (standard filenames).

    ``names`` defaults to all of ``CONFIG_FILES``. Files that are written on load
    are materialized first; ``excluded.csv`` is exported only if it exists.
    Returns the list of filenames actually written.
    """
    from core import storage as _st
    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)
    targets = names if names is not None else CONFIG_FILES
    written: list[str] = []
    for name in targets:
        loader = _CONFIG_LOADERS.get(name)
        src = _st._path(name)
        if loader is not None and not src.exists():
            try:
                getattr(_st, loader)()   # write defaults to DATA_DIR
            except Exception as exc:
                _log.warning("export: could not materialize %s: %s", name, exc)
        if src.exists():
            try:
                shutil.copy2(str(src), str(dest / name))
                written.append(name)
            except Exception as exc:
                _log.warning("export: copy %s failed: %s", name, exc)
    return written


def import_config_from_dir(src_dir) -> list[str]:
    """Copy each standard config CSV found in ``src_dir`` into ``DATA_DIR``.

    Unknown / missing / unreadable files are skipped (never raised). Returns the
    list of filenames actually imported.
    """
    from core import storage as _st
    src = Path(src_dir)
    imported: list[str] = []
    for name in CONFIG_FILES:
        candidate = src / name
        if not candidate.exists():
            continue
        if not _looks_like_csv(candidate):
            _log.warning("import: %s is not a readable CSV; skipping", name)
            continue
        try:
            shutil.copy2(str(candidate), str(_st._path(name)))
            imported.append(name)
        except Exception as exc:
            _log.warning("import: copy %s failed: %s", name, exc)
    return imported
