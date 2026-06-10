"""storage facade.

Single source of truth for ``DATA_DIR`` and all path-resolution / coercion
primitives. Group IO lives in sibling modules (``storage_config`` /
``storage_selectors`` / ``storage_results`` / ``storage_state``) and is
re-exported here so consumers and tests keep calling ``core.storage.*``.

⚠️ Keep this a ``.py`` module (facade), never a package: tests rely on
``monkeypatch.setattr(storage, "DATA_DIR", tmp_path)`` and on patching
``core.storage.save_state`` etc. Sibling modules never reference ``DATA_DIR``
directly — they route through the primitives below so the monkeypatch applies
to every load/save.
"""

import csv
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"


# ── Path / coercion primitives (single source of truth) ────────────────────────

def _ensure_data_dir():
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _path(filename: str) -> Path:
    """Resolve a data file path against the (monkeypatchable) DATA_DIR.

    Single source of truth for file location so that
    ``monkeypatch.setattr(storage, "DATA_DIR", tmp_path)`` applies everywhere,
    including sibling modules that route through this primitive.
    """
    _ensure_data_dir()
    return DATA_DIR / filename


def _coerce(value: str):
    """Convert CSV string to int, float, or keep as str."""
    if not isinstance(value, str):
        return value
    stripped = value.strip()
    try:
        return int(stripped)
    except (ValueError, TypeError):
        pass
    try:
        return float(stripped)
    except (ValueError, TypeError):
        pass
    return stripped


# ── Generic key,value CSV helpers (web/flow/target/settings) ───────────────────

def _kv_defaults(defaults: list[tuple[str, str]]) -> dict:
    return {k: _coerce(v) for k, v in defaults}


def _load_kv(filename: str, defaults: list[tuple[str, str]]) -> dict:
    """Load a key,value CSV; write defaults if missing; merge missing keys."""
    path = _path(filename)
    result = _kv_defaults(defaults)
    if not path.exists():
        _save_kv(filename, result)
        return result
    try:
        with open(path, newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                k = (row.get("key") or "").strip()
                v = (row.get("value") or "").strip()
                if k:
                    result[k] = _coerce(v)
    except Exception:
        pass
    return result


def _save_kv(filename: str, data: dict):
    path = _path(filename)
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["key", "value"])
        for k, v in data.items():
            writer.writerow([k, v])


# ── Results path primitive (§3.1) — stays in facade as path single-source ───────

def results_path() -> Path:
    return _path("results.csv")


# ── Sibling module re-exports (defined after primitives; no import cycle) ───────

# Config groups: settings / web / flow / target / delays (§2)
from core.storage_config import (  # noqa: E402
    settings_defaults, load_settings, save_settings,
    web_defaults, load_web, save_web,
    flow_defaults, load_flow, save_flow,
    target_defaults, load_target, save_target,
    delay_defaults, load_delays, save_delays,
    fields_defaults, load_fields, save_fields,
)

# Collectable-field name list (Fix-2 B)
from core.storage_defaults import COLLECT_FIELDS  # noqa: E402,F401

# Selectors (§2.2 — priority fallback 체인)
from core.storage_selectors import (  # noqa: E402
    selector_defaults, _normalize_selector_row, load_selectors, save_selectors,
)

# Flow steps (260610-4 — data-driven flow) + action vocabulary
from core.storage_defaults import FLOW_ACTIONS  # noqa: E402,F401
from core.storage_flowsteps import (  # noqa: E402
    flow_steps_defaults, load_flow_steps, save_flow_steps,
)

# Folder-based config sharing (260610-4)
from core.storage_share import (  # noqa: E402
    CONFIG_FILES, DATA_FILES, SHAREABLE_FILES, SHAREABLE_LABELS,
    export_config_to_dir, import_config_from_dir,
    export_config_to_zip, import_config_from_zip,
)

# Results / Excluded (§3.1 / §3.2)
from core.storage_results import (  # noqa: E402
    load_excluded, save_excluded,
    load_results, seen_usernames, append_result, export_results,
)

# State (§3.3 — 재개용 진행 상태)
from core.storage_state import load_state, save_state, clear_state  # noqa: E402
