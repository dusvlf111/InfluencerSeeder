import csv
from pathlib import Path

from core.storage_defaults import (
    _SETTINGS_DEFAULTS,
    _WEB_DEFAULTS,
    _FLOW_DEFAULTS,
    _TARGET_DEFAULTS,
    _DELAY_DEFAULTS,
    _SELECTOR_DEFAULTS,
    _SELECTOR_FIELDNAMES,
)

DATA_DIR = Path(__file__).parent / "data"


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


# ── Settings (v2 — 유지, 마이그레이션 호환) ─────────────────────────────────────

def settings_defaults() -> dict:
    return {k: _coerce(v) for k, v in _SETTINGS_DEFAULTS}


def load_settings() -> dict:
    path = _path("settings.csv")
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
                    result[k] = _coerce(v)
    except Exception:
        pass
    return result


def save_settings(data: dict):
    _save_kv("settings.csv", data)


# ── Web settings (§2.1) ────────────────────────────────────────────────────────

def web_defaults() -> dict:
    return _kv_defaults(_WEB_DEFAULTS)


def load_web() -> dict:
    return _load_kv("web.csv", _WEB_DEFAULTS)


def save_web(data: dict):
    _save_kv("web.csv", data)


# ── Flow settings (§2.4) ───────────────────────────────────────────────────────

def flow_defaults() -> dict:
    return _kv_defaults(_FLOW_DEFAULTS)


def load_flow() -> dict:
    return _load_kv("flow.csv", _FLOW_DEFAULTS)


def save_flow(data: dict):
    _save_kv("flow.csv", data)


# ── Target settings (§2.5) ─────────────────────────────────────────────────────

def target_defaults() -> dict:
    return _kv_defaults(_TARGET_DEFAULTS)


def load_target() -> dict:
    return _load_kv("target.csv", _TARGET_DEFAULTS)


def save_target(data: dict):
    _save_kv("target.csv", data)


# ── Delays (§2.3) ──────────────────────────────────────────────────────────────

def delay_defaults() -> dict:
    return {k: (float(lo), float(hi)) for k, (lo, hi) in _DELAY_DEFAULTS}


def load_delays() -> dict:
    """Return {step_id: (delay_min, delay_max)}; defaults merged on missing/corrupt."""
    path = _path("delays.csv")
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
                lo = _coerce(row.get("delay_min") or "")
                hi = _coerce(row.get("delay_max") or "")
                base_lo, base_hi = result.get(sid, (0.0, 0.0))
                lo = float(lo) if isinstance(lo, (int, float)) else base_lo
                hi = float(hi) if isinstance(hi, (int, float)) else base_hi
                result[sid] = (lo, hi)
    except Exception:
        pass
    return result


def save_delays(data: dict):
    path = _path("delays.csv")
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["step_id", "delay_min", "delay_max"])
        for sid, pair in data.items():
            lo, hi = pair
            writer.writerow([sid, lo, hi])


# ── Selectors (§2.2 — priority fallback 체인) ──────────────────────────────────

def selector_defaults() -> list[dict]:
    return [dict(row) for row in _SELECTOR_DEFAULTS]


def _normalize_selector_row(row: dict) -> dict:
    out = {k: (row.get(k) if row.get(k) is not None else "") for k in _SELECTOR_FIELDNAMES}
    # priority: 결측/비숫자 → 1 (하위호환), int 화
    prio = _coerce(out.get("priority") or "")
    out["priority"] = prio if isinstance(prio, int) else 1
    return out


def load_selectors() -> list[dict]:
    """Load selectors; sorted by (step_id stable order, priority asc)."""
    path = _path("selectors.csv")
    if not path.exists():
        save_selectors(_SELECTOR_DEFAULTS)
        return selector_defaults()
    try:
        rows = []
        with open(path, newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                rows.append(_normalize_selector_row(row))
        if not rows:
            return selector_defaults()
    except Exception:
        return selector_defaults()
    # priority 오름차순 정렬 (결측은 9999). step_id 첫 등장 순서를 안정 유지.
    order: dict[str, int] = {}
    for r in rows:
        order.setdefault(r["step_id"], len(order))
    rows.sort(key=lambda r: (
        order[r["step_id"]],
        r["priority"] if isinstance(r["priority"], int) else 9999,
    ))
    return rows


def save_selectors(rows: list[dict]):
    path = _path("selectors.csv")
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=_SELECTOR_FIELDNAMES, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            out = dict(row)
            if not str(out.get("priority", "")).strip():
                out["priority"] = 1
            writer.writerow(out)


# ── Results path primitive (§3.1) — stays in facade as path single-source ───────

def results_path() -> Path:
    return _path("results.csv")


# ── Sibling module re-exports (defined after primitives; no import cycle) ───────

# State (§3.3 — 재개용 진행 상태)
from core.storage_state import load_state, save_state, clear_state  # noqa: E402

# Results / Excluded (§3.1 / §3.2)
from core.storage_results import (  # noqa: E402
    load_excluded, save_excluded,
    load_results, seen_usernames, append_result, export_results,
)
