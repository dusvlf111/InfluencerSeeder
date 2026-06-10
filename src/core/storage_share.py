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
import zipfile
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


# ── Single-file (zip) config sharing ───────────────────────────────────────────

def export_config_to_zip(zip_path, names: list[str] | None = None) -> list[str]:
    """Bundle the requested config CSVs into a single ``.zip`` at ``zip_path``.

    Same materialization rules as :func:`export_config_to_dir` (files written on
    load are created first; ``excluded.csv`` only if it exists). Each CSV is
    stored flat under its standard filename. Returns the filenames bundled.
    """
    from core import storage as _st
    targets = names if names is not None else CONFIG_FILES
    zp = Path(zip_path)
    if zp.parent and not zp.parent.exists():
        zp.parent.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    with zipfile.ZipFile(str(zp), "w", zipfile.ZIP_DEFLATED) as zf:
        for name in targets:
            loader = _CONFIG_LOADERS.get(name)
            src = _st._path(name)
            if loader is not None and not src.exists():
                try:
                    getattr(_st, loader)()   # write defaults to DATA_DIR
                except Exception as exc:
                    _log.warning("export-zip: could not materialize %s: %s", name, exc)
            if src.exists():
                try:
                    zf.write(str(src), arcname=name)
                    written.append(name)
                except Exception as exc:
                    _log.warning("export-zip: add %s failed: %s", name, exc)
    return written


def import_config_from_zip(zip_path) -> list[str]:
    """Apply standard config CSVs found inside a ``.zip`` into ``DATA_DIR``.

    Matches members by basename (tolerates flat or nested archives). Unknown /
    unreadable / non-CSV members are skipped (never raised). Returns the list of
    filenames actually imported.
    """
    from core import storage as _st
    imported: list[str] = []
    try:
        zf = zipfile.ZipFile(str(zip_path))
    except Exception as exc:
        _log.warning("import-zip: cannot open %s: %s", zip_path, exc)
        return imported
    with zf:
        by_base: dict[str, str] = {}
        for member in zf.namelist():
            by_base.setdefault(Path(member).name, member)
        for name in CONFIG_FILES:
            member = by_base.get(name)
            if member is None:
                continue
            try:
                data = zf.read(member)
            except Exception as exc:
                _log.warning("import-zip: read %s failed: %s", name, exc)
                continue
            # Light CSV validation: decodable text with a parseable header row.
            try:
                text = data.decode("utf-8-sig")
                if next(csv.reader(text.splitlines()), None) is None:
                    _log.warning("import-zip: %s has no header; skipping", name)
                    continue
            except Exception:
                _log.warning("import-zip: %s is not readable text; skipping", name)
                continue
            try:
                with open(_st._path(name), "wb") as f:
                    f.write(data)
                imported.append(name)
            except Exception as exc:
                _log.warning("import-zip: write %s failed: %s", name, exc)
    return imported
