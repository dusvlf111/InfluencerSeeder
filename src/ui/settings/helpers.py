"""SettingsView 믹스인 공용 헬퍼/상수."""

_BROWSERS = ["chrome", "edge", "firefox"]
_MODES = ["hashtag", "keyword"]


def _as_bool(v) -> bool:
    """storage 의 bool 값은 문자열('true'/'false')로 로드된다 — 통일 해석."""
    return str(v).strip().lower() == "true"
