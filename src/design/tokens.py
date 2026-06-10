"""Design tokens — single source of truth for all visual constants."""
from dataclasses import dataclass


@dataclass(frozen=True)
class _Colors:
    bg: str = "#0d0d0f"
    surface: str = "#161618"
    surface2: str = "#1e1e21"
    border: str = "#2a2a2e"
    accent: str = "#7c6af7"
    accent_light: str = "#a99bf9"
    green: str = "#4ade80"
    red: str = "#f87171"
    amber: str = "#fbbf24"
    text: str = "#f0eff5"
    muted: str = "#6b6a72"
    muted2: str = "#9997a3"


@dataclass(frozen=True)
class _Typography:
    family: str = "'Pretendard', 'Apple SD Gothic Neo', 'Malgun Gothic', sans-serif"
    family_mono: str = "'Menlo', 'Consolas', monospace"
    size_base: int = 13
    size_small: int = 12
    size_large: int = 16


@dataclass(frozen=True)
class _Spacing:
    xs: int = 4
    sm: int = 8
    md: int = 12
    lg: int = 16
    xl: int = 24


@dataclass(frozen=True)
class _Radius:
    sm: int = 4
    md: int = 6
    lg: int = 8
    xl: int = 16


Colors = _Colors()
Typography = _Typography()
Spacing = _Spacing()
Radius = _Radius()
