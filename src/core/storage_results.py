"""results.csv (profile rows + dedup) and excluded.csv IO (§3.1 / §3.2).

All file access routes through ``core.storage`` primitives
(``_path`` / ``results_path``) so the
``monkeypatch.setattr(storage, "DATA_DIR", tmp_path)`` contract holds.
The facade import happens inside functions to avoid an import-time cycle.

NOTE: ``results_path`` itself stays in ``core.storage`` as a path primitive.
dedup / username normalization behavior is unchanged from the original.
"""

import csv
import shutil

from core.storage_defaults import _RESULTS_FIELDNAMES


# ── Excluded accounts (§3.2 — v2 유지) ──────────────────────────────────────────

def load_excluded() -> list[str]:
    from core import storage as _st
    path = _st._path("excluded.csv")
    if not path.exists():
        return []
    try:
        accounts = []
        with open(path, newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                u = (row.get("username") or "").strip()
                if u:
                    accounts.append(u)
        return accounts
    except Exception:
        return []


def save_excluded(accounts: list[str]):
    from core import storage as _st
    path = _st._path("excluded.csv")
    clean = sorted(set(a.strip() for a in accounts if a.strip()))
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["username"])
        writer.writeheader()
        for u in clean:
            writer.writerow({"username": u})


# ── Results (§3.1 — 프로필 중심 + dedup) ────────────────────────────────────────

def load_results() -> list[dict]:
    from core import storage as _st
    path = _st.results_path()
    if not path.exists():
        return []
    try:
        rows = []
        with open(path, newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                rows.append(dict(row))
        return rows
    except Exception:
        return []


def seen_usernames() -> set[str]:
    """Lower-cased union of results.csv usernames and excluded.csv usernames."""
    seen: set[str] = set()
    for r in load_results():
        u = (r.get("username") or "").strip().lower()
        if u:
            seen.add(u)
    for u in load_excluded():
        u = (u or "").strip().lower()
        if u:
            seen.add(u)
    return seen


def append_result(info: dict) -> bool:
    """Append a profile row if username is not already seen.

    Returns True if appended (new), False if a duplicate (results ∪ excluded).
    Username is normalized to lower-case before comparison/storage.
    """
    from core import storage as _st
    username = (info.get("username") or "").strip()
    if not username:
        return False
    if username.lower() in seen_usernames():
        return False

    row = {k: info.get(k, "") for k in _RESULTS_FIELDNAMES}
    row["username"] = username.lower()

    path = _st.results_path()
    is_new = not path.exists()
    with open(path, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=_RESULTS_FIELDNAMES, extrasaction="ignore")
        if is_new:
            writer.writeheader()
        writer.writerow(row)
    return True


def export_results(dest_path: str):
    """Copy results.csv to dest_path."""
    from core import storage as _st
    src = _st.results_path()
    if not src.exists():
        raise FileNotFoundError(f"No results file: {src}")
    shutil.copy2(str(src), dest_path)
