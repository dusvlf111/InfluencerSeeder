"""Setting-group IO: settings / web / flow / target / delays (§2).

All file access and value-coercion route through ``core.storage`` primitives
(``_path`` / ``_load_kv`` / ``_save_kv`` / ``_kv_defaults`` / ``_coerce``) so the
``monkeypatch.setattr(storage, "DATA_DIR", tmp_path)`` contract holds.
The facade import happens inside functions to avoid an import-time cycle.
load/save/merge/coerce behavior is unchanged from the original.
"""

import csv

from core.storage_defaults import (
    _SETTINGS_DEFAULTS,
    _WEB_DEFAULTS,
    _FLOW_DEFAULTS,
    _TARGET_DEFAULTS,
    _DELAY_DEFAULTS,
)


# ── Settings (v2 — 유지, 마이그레이션 호환) ─────────────────────────────────────

def settings_defaults() -> dict:
    from core import storage as _st
    return {k: _st._coerce(v) for k, v in _SETTINGS_DEFAULTS}


def load_settings() -> dict:
    from core import storage as _st
    path = _st._path("settings.csv")
    result = settings_defaults()
    if not path.exists():
        save_settings(result)
        return result
    try:
        with open(path, newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                k = (row.get("key") or "").strip()
                v = (row.get("value") or "").strip()
                if k:
                    result[k] = _st._coerce(v)
    except Exception:
        pass
    return result


def save_settings(data: dict):
    from core import storage as _st
    _st._save_kv("settings.csv", data)


# ── Web settings (§2.1) ────────────────────────────────────────────────────────

def web_defaults() -> dict:
    from core import storage as _st
    return _st._kv_defaults(_WEB_DEFAULTS)


def load_web() -> dict:
    from core import storage as _st
    return _st._load_kv("web.csv", _WEB_DEFAULTS)


def save_web(data: dict):
    from core import storage as _st
    _st._save_kv("web.csv", data)


# ── Flow settings (§2.4) ───────────────────────────────────────────────────────

def flow_defaults() -> dict:
    from core import storage as _st
    return _st._kv_defaults(_FLOW_DEFAULTS)


def load_flow() -> dict:
    from core import storage as _st
    return _st._load_kv("flow.csv", _FLOW_DEFAULTS)


def save_flow(data: dict):
    from core import storage as _st
    _st._save_kv("flow.csv", data)


# ── Target settings (§2.5) ─────────────────────────────────────────────────────

def target_defaults() -> dict:
    from core import storage as _st
    return _st._kv_defaults(_TARGET_DEFAULTS)


def load_target() -> dict:
    from core import storage as _st
    return _st._load_kv("target.csv", _TARGET_DEFAULTS)


def save_target(data: dict):
    from core import storage as _st
    _st._save_kv("target.csv", data)


# ── Delays (§2.3) ──────────────────────────────────────────────────────────────

def delay_defaults() -> dict:
    return {k: (float(lo), float(hi)) for k, (lo, hi) in _DELAY_DEFAULTS}


def load_delays() -> dict:
    """Return {step_id: (delay_min, delay_max)}; defaults merged on missing/corrupt."""
    from core import storage as _st
    path = _st._path("delays.csv")
    result = delay_defaults()
    if not path.exists():
        save_delays(result)
        return result
    try:
        with open(path, newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                sid = (row.get("step_id") or "").strip()
                if not sid:
                    continue
                lo = _st._coerce(row.get("delay_min") or "")
                hi = _st._coerce(row.get("delay_max") or "")
                base_lo, base_hi = result.get(sid, (0.0, 0.0))
                lo = float(lo) if isinstance(lo, (int, float)) else base_lo
                hi = float(hi) if isinstance(hi, (int, float)) else base_hi
                result[sid] = (lo, hi)
    except Exception:
        pass
    return result


def save_delays(data: dict):
    from core import storage as _st
    path = _st._path("delays.csv")
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["step_id", "delay_min", "delay_max"])
        for sid, pair in data.items():
            lo, hi = pair
            writer.writerow([sid, lo, hi])
