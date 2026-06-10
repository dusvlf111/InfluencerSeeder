"""flow_steps.csv IO (260610-4 — data-driven flow).

An ordered list of steps the engine interprets at run time. Mirrors the
``storage_selectors`` style: file access and ``_coerce`` route through
``core.storage`` so the ``monkeypatch.setattr(storage, "DATA_DIR", tmp_path)``
contract holds. Rows are returned sorted by ``order``; ``enabled`` is normalized
to bool and rows whose ``action`` is unknown are dropped (logged, never raised).
"""

import csv
import logging

from core.storage_defaults import (
    _FLOW_STEPS_DEFAULTS,
    _FLOW_STEPS_FIELDNAMES,
    FLOW_ACTIONS,
)

_log = logging.getLogger(__name__)

_TRUE = {"true", "1", "yes", "y", "t"}


def flow_steps_defaults() -> list[dict]:
    return [dict(row) for row in _FLOW_STEPS_DEFAULTS]


def _normalize_row(row: dict) -> dict | None:
    """Coerce a raw CSV row to the canonical schema; None if it should be dropped."""
    from core import storage as _st
    out = {k: (row.get(k) if row.get(k) is not None else "") for k in _FLOW_STEPS_FIELDNAMES}

    action = str(out.get("action") or "").strip()
    if action not in FLOW_ACTIONS:
        _log.warning("flow_steps: dropping row with unknown action %r", action)
        return None
    out["action"] = action

    order = _st._coerce(out.get("order") or "")
    out["order"] = order if isinstance(order, int) else 0

    enabled = out.get("enabled")
    if isinstance(enabled, bool):
        pass
    else:
        out["enabled"] = str(enabled).strip().lower() in _TRUE

    out["phase"] = str(out.get("phase") or "per_post").strip() or "per_post"
    out["step_name"] = str(out.get("step_name") or "")
    out["selector_ref"] = str(out.get("selector_ref") or "")
    out["param"] = str(out.get("param") or "")
    return out


def load_flow_steps() -> list[dict]:
    """Load flow steps sorted by ``order``; write defaults when missing/empty."""
    from core import storage as _st
    path = _st._path("flow_steps.csv")
    if not path.exists():
        save_flow_steps(_FLOW_STEPS_DEFAULTS)
        return flow_steps_defaults()
    try:
        rows: list[dict] = []
        with open(path, newline="", encoding="utf-8-sig") as f:
            for raw in csv.DictReader(f):
                norm = _normalize_row(raw)
                if norm is not None:
                    rows.append(norm)
        if not rows:
            return flow_steps_defaults()
    except Exception:
        return flow_steps_defaults()
    rows.sort(key=lambda r: r["order"] if isinstance(r["order"], int) else 9999)
    return rows


def save_flow_steps(rows: list[dict]):
    from core import storage as _st
    path = _st._path("flow_steps.csv")
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=_FLOW_STEPS_FIELDNAMES, extrasaction="ignore")
        writer.writeheader()
        for i, row in enumerate(rows, start=1):
            out = dict(row)
            if not str(out.get("order", "")).strip():
                out["order"] = i
            enabled = out.get("enabled", True)
            if isinstance(enabled, bool):
                out["enabled"] = "true" if enabled else "false"
            else:
                out["enabled"] = "true" if str(enabled).strip().lower() in _TRUE else "false"
            writer.writerow(out)
