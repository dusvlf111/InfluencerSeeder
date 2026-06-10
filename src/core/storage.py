import csv
import json
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

# ── v3 setting group defaults (§2) ─────────────────────────────────────────────

_WEB_DEFAULTS: list[tuple[str, str]] = [
    ("browser",              "chrome"),
    ("headless",             "false"),
    ("window_width",         "1280"),
    ("window_height",        "900"),
    ("randomize_window",     "true"),
    ("randomize_user_agent", "true"),
    ("user_data_dir",        ""),
    ("locale",               "ko-KR"),
    ("implicit_wait",        "5"),
    ("page_load_timeout",    "30"),
]

_FLOW_DEFAULTS: list[tuple[str, str]] = [
    ("max_tags",                 "3"),
    ("tag_start_index",          "0"),
    ("posts_per_tag",            "5"),
    ("scroll_max_attempts",      "15"),
    ("skip_visited_profile",     "true"),
    ("stop_on_consecutive_miss", "10"),
]

_TARGET_DEFAULTS: list[tuple[str, str]] = [
    ("min_followers", "0"),
    ("max_followers", "0"),
    ("min_following", "0"),
    ("max_following", "0"),
    ("min_posts",     "0"),
    ("keyword",       ""),
    ("mode",          "hashtag"),
]

# (step_id, (delay_min, delay_max)) per PRD §2.3
_DELAY_DEFAULTS: list[tuple[str, tuple[float, float]]] = [
    ("step1",       (1.0, 2.5)),
    ("step2",       (0.5, 1.5)),
    ("step3",       (2.0, 4.0)),
    ("step4",       (1.5, 3.0)),
    ("step5",       (2.0, 4.0)),
    ("step6",       (0.5, 1.5)),
    ("back",        (1.0, 2.5)),
    ("scroll",      (0.8, 2.0)),
    ("typing_char", (0.05, 0.18)),
]

# ── Selectors (§2.2) — step 당 priority 정렬 fallback 체인 ──────────────────────

_SELECTOR_DEFAULTS: list[dict] = [
    {
        "step_id": "search_icon", "step_name": "돋보기 클릭(Step1)", "priority": 1,
        "selector_type": "xpath",
        "selector_value": "//a[contains(@href,'/explore/')]//*[name()='svg' and @aria-label='검색']",
    },
    {
        "step_id": "search_icon", "step_name": "돋보기 클릭(Step1)", "priority": 2,
        "selector_type": "xpath",
        "selector_value": "//a[contains(@href,'/search')]",
    },
    {
        "step_id": "search_icon", "step_name": "돋보기 클릭(Step1)", "priority": 3,
        "selector_type": "css",
        "selector_value": "svg[aria-label='Search']",
    },
    {
        "step_id": "search_input", "step_name": "검색 입력(Step2)", "priority": 1,
        "selector_type": "xpath",
        "selector_value": "//input[@placeholder='검색']",
    },
    {
        "step_id": "search_input", "step_name": "검색 입력(Step2)", "priority": 2,
        "selector_type": "xpath",
        "selector_value": "//input[@placeholder='Search']",
    },
    {
        "step_id": "tag_result", "step_name": "태그 클릭(Step3)", "priority": 1,
        "selector_type": "xpath",
        "selector_value": "//a[contains(@href,'/explore/tags/')]",
    },
    {
        "step_id": "post_link", "step_name": "이미지 클릭(Step4)", "priority": 1,
        "selector_type": "xpath",
        "selector_value": "//a[contains(@href,'/p/')]",
    },
    {
        "step_id": "profile_link", "step_name": "프로필 클릭(Step5)", "priority": 1,
        "selector_type": "css",
        "selector_value": "header a[href]:not([href='/'])",
    },
    {
        "step_id": "username_text", "step_name": "유저네임", "priority": 1,
        "selector_type": "css",
        "selector_value": "header h2, header h1",
    },
    {
        "step_id": "followers_count", "step_name": "팔로워 수", "priority": 1,
        "selector_type": "xpath",
        "selector_value": "//a[contains(@href,'/followers/')]//span[@title]",
    },
    {
        "step_id": "following_count", "step_name": "팔로우 수", "priority": 1,
        "selector_type": "xpath",
        "selector_value": "//a[contains(@href,'/following/')]//span",
    },
    {
        "step_id": "posts_count", "step_name": "게시물 수", "priority": 1,
        "selector_type": "xpath",
        "selector_value": "//header//li[1]//span//span",
    },
    {
        "step_id": "bio_text", "step_name": "소개글", "priority": 1,
        "selector_type": "css",
        "selector_value": "header section > div:last-child",
    },
    {
        "step_id": "website_link", "step_name": "웹사이트", "priority": 1,
        "selector_type": "css",
        "selector_value": "header a[href*='http']:not([href*='instagram.com'])",
    },
]

# v3 프로필 중심 스키마 (§3.1)
_RESULTS_FIELDNAMES = [
    "username", "full_name", "followers", "following", "posts_count",
    "bio", "website", "is_private", "profile_url",
    "source_tag", "source_post_url", "collected_at",
]

_SELECTOR_FIELDNAMES = ["step_id", "step_name", "priority", "selector_type", "selector_value"]


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


# ── Generic key,value CSV helpers (web/flow/target/settings) ───────────────────

def _kv_defaults(defaults: list[tuple[str, str]]) -> dict:
    return {k: _coerce(v) for k, v in defaults}


def _load_kv(filename: str, defaults: list[tuple[str, str]]) -> dict:
    """Load a key,value CSV; write defaults if missing; merge missing keys."""
    _ensure_data_dir()
    path = DATA_DIR / filename
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
    _ensure_data_dir()
    path = DATA_DIR / filename
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["key", "value"])
        for k, v in data.items():
            writer.writerow([k, v])


# ── Settings (v2 — 유지, 마이그레이션 호환) ─────────────────────────────────────

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
    _ensure_data_dir()
    path = DATA_DIR / "delays.csv"
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
    _ensure_data_dir()
    path = DATA_DIR / "delays.csv"
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
    _ensure_data_dir()
    path = DATA_DIR / "selectors.csv"
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
    _ensure_data_dir()
    path = DATA_DIR / "selectors.csv"
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=_SELECTOR_FIELDNAMES, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            out = dict(row)
            if not str(out.get("priority", "")).strip():
                out["priority"] = 1
            writer.writerow(out)


# ── Excluded accounts (§3.2 — v2 유지) ──────────────────────────────────────────

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


# ── Results (§3.1 — 프로필 중심 + dedup) ────────────────────────────────────────

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
    username = (info.get("username") or "").strip()
    if not username:
        return False
    if username.lower() in seen_usernames():
        return False

    row = {k: info.get(k, "") for k in _RESULTS_FIELDNAMES}
    row["username"] = username.lower()

    path = results_path()
    is_new = not path.exists()
    with open(path, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=_RESULTS_FIELDNAMES, extrasaction="ignore")
        if is_new:
            writer.writeheader()
        writer.writerow(row)
    return True


def export_results(dest_path: str):
    """Copy results.csv to dest_path."""
    src = results_path()
    if not src.exists():
        raise FileNotFoundError(f"No results file: {src}")
    shutil.copy2(str(src), dest_path)


# ── State (§3.3 — 재개용 진행 상태) ─────────────────────────────────────────────

def load_state() -> dict | None:
    """Return resume state dict, or None if missing/corrupt."""
    _ensure_data_dir()
    path = DATA_DIR / "state.json"
    if not path.exists():
        return None
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def save_state(data: dict):
    _ensure_data_dir()
    path = DATA_DIR / "state.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def clear_state():
    _ensure_data_dir()
    path = DATA_DIR / "state.json"
    Path(path).unlink(missing_ok=True)
