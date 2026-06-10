import csv
import shutil
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"

_SETTINGS_DEFAULTS: list[tuple[str, str]] = [
    ("min_followers",   "0"),
    ("max_followers",   "0"),
    ("posts_per_tag",   "5"),
    ("max_tags",        "3"),
    ("step1_delay_min", "1.0"),
    ("step1_delay_max", "2.5"),
    ("step2_delay_min", "0.5"),
    ("step2_delay_max", "1.5"),
    ("step3_delay_min", "2.0"),
    ("step3_delay_max", "4.0"),
    ("step4_delay_min", "1.5"),
    ("step4_delay_max", "3.0"),
    ("step5_delay_min", "2.0"),
    ("step5_delay_max", "4.0"),
    ("step6_delay_min", "0.5"),
    ("step6_delay_max", "1.5"),
    ("back_delay_min",  "1.0"),
    ("back_delay_max",  "2.5"),
]

_SELECTOR_DEFAULTS: list[dict] = [
    {
        "step_id": "search_icon",
        "step_name": "Search Icon (Step 1)",
        "selector_type": "xpath",
        "selector_value": (
            "//a[contains(@href,'/search')] | "
            "//span[@role='link' and contains(.,'Search')]"
        ),
    },
    {
        "step_id": "search_input",
        "step_name": "Search Input (Step 2)",
        "selector_type": "xpath",
        "selector_value": "//input[@placeholder='Search' or @placeholder='검색']",
    },
    {
        "step_id": "tag_result",
        "step_name": "Tag Suggestion (Step 3)",
        "selector_type": "xpath",
        "selector_value": "//a[contains(@href, '/explore/tags/')]",
    },
    {
        "step_id": "post_link",
        "step_name": "Post Link (Step 4)",
        "selector_type": "xpath",
        "selector_value": "//a[contains(@href, '/p/')]",
    },
    {
        "step_id": "profile_link",
        "step_name": "Profile Link in Post (Step 5)",
        "selector_type": "css",
        "selector_value": "header a[href]:not([href='/'])",
    },
]

_RESULTS_FIELDNAMES = [
    "username", "followers", "following", "posts_count",
    "bio", "website", "post_url", "profile_url", "collected_at",
]

_SELECTOR_FIELDNAMES = ["step_id", "step_name", "selector_type", "selector_value"]


def _ensure_data_dir():
    DATA_DIR.mkdir(parents=True, exist_ok=True)


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


# ── Settings ──────────────────────────────────────────────────────────────────

def settings_defaults() -> dict:
    return {k: _coerce(v) for k, v in _SETTINGS_DEFAULTS}


def load_settings() -> dict:
    _ensure_data_dir()
    path = DATA_DIR / "settings.csv"
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
    _ensure_data_dir()
    path = DATA_DIR / "settings.csv"
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["key", "value"])
        for k, v in data.items():
            writer.writerow([k, v])


# ── Selectors ─────────────────────────────────────────────────────────────────

def selector_defaults() -> list[dict]:
    return [dict(row) for row in _SELECTOR_DEFAULTS]


def load_selectors() -> list[dict]:
    _ensure_data_dir()
    path = DATA_DIR / "selectors.csv"
    if not path.exists():
        save_selectors(_SELECTOR_DEFAULTS)
        return selector_defaults()
    try:
        rows = []
        with open(path, newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                rows.append({k: (row.get(k) or "") for k in _SELECTOR_FIELDNAMES})
        return rows or selector_defaults()
    except Exception:
        return selector_defaults()


def save_selectors(rows: list[dict]):
    _ensure_data_dir()
    path = DATA_DIR / "selectors.csv"
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=_SELECTOR_FIELDNAMES, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


# ── Excluded accounts ─────────────────────────────────────────────────────────

def load_excluded() -> list[str]:
    _ensure_data_dir()
    path = DATA_DIR / "excluded.csv"
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
    _ensure_data_dir()
    path = DATA_DIR / "excluded.csv"
    clean = sorted(set(a.strip() for a in accounts if a.strip()))
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["username"])
        writer.writeheader()
        for u in clean:
            writer.writerow({"username": u})


# ── Results ───────────────────────────────────────────────────────────────────

def results_path() -> Path:
    _ensure_data_dir()
    return DATA_DIR / "results.csv"


def load_results() -> list[dict]:
    path = results_path()
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


def append_result(info: dict):
    path = results_path()
    is_new = not path.exists()
    with open(path, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=_RESULTS_FIELDNAMES, extrasaction="ignore")
        if is_new:
            writer.writeheader()
        writer.writerow({k: info.get(k, "") for k in _RESULTS_FIELDNAMES})


def export_results(dest_path: str):
    """Copy results.csv to dest_path."""
    src = results_path()
    if not src.exists():
        raise FileNotFoundError(f"No results file: {src}")
    shutil.copy2(str(src), dest_path)
