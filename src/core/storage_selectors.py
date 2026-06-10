"""selectors.csv IO (§2.2 — priority fallback 체인).

File access and the ``_coerce`` primitive route through ``core.storage``
so the ``monkeypatch.setattr(storage, "DATA_DIR", tmp_path)`` contract holds.
The facade import happens inside functions to avoid an import-time cycle.
priority sorting behavior is unchanged from the original.
"""

import csv

from core.storage_defaults import _SELECTOR_DEFAULTS, _SELECTOR_FIELDNAMES


def selector_defaults() -> list[dict]:
    return [dict(row) for row in _SELECTOR_DEFAULTS]


def normalize_selector_value(value) -> str:
    """Sanitize a pasted selector_value.

    양끝 공백을 strip 하고 내부의 ``\\r`` / ``\\n`` / ``\\t`` 를 제거(빈 문자열로
    replace)한다. **내부의 일반 스페이스는 보존** — CSS 자손결합자(``header a``),
    XPath 술어(``[@title='a b']``), 콤마 구분(``header h2, header h1``)이 붙여넣기
    중 섞인 줄바꿈/탭 때문에 깨지는 것만 방지한다.

    예) ``" /html/a\\nb "`` → ``"/html/ab"`` , ``"/a b"`` → ``"/a b"`` .
    """
    if value is None:
        return ""
    text = str(value).strip()
    for ws in ("\r", "\n", "\t"):
        text = text.replace(ws, "")
    return text


def _normalize_selector_row(row: dict) -> dict:
    from core import storage as _st
    out = {k: (row.get(k) if row.get(k) is not None else "") for k in _SELECTOR_FIELDNAMES}
    # priority: 결측/비숫자 → 1 (하위호환), int 화
    prio = _st._coerce(out.get("priority") or "")
    out["priority"] = prio if isinstance(prio, int) else 1
    # selector_value: 붙여넣기 시 섞인 줄바꿈/탭 제거(스페이스는 보존).
    out["selector_value"] = normalize_selector_value(out.get("selector_value"))
    # 식별/타입 필드는 strip 정도로 줄바꿈 잔재만 제거.
    for k in ("step_id", "step_name", "selector_type"):
        out[k] = str(out.get(k) or "").strip()
    return out


def load_selectors() -> list[dict]:
    """Load selectors; sorted by (step_id stable order, priority asc)."""
    from core import storage as _st
    path = _st._path("selectors.csv")
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
    from core import storage as _st
    path = _st._path("selectors.csv")
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=_SELECTOR_FIELDNAMES, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            out = dict(row)
            if not str(out.get("priority", "")).strip():
                out["priority"] = 1
            # 저장 경로에서도 selector_value 정규화(줄바꿈/탭 제거, 스페이스 보존).
            out["selector_value"] = normalize_selector_value(out.get("selector_value"))
            for k in ("step_id", "step_name", "selector_type"):
                if k in out:
                    out[k] = str(out.get(k) or "").strip()
            writer.writerow(out)
