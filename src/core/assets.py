"""Bundled asset path resolution.

Resolves paths to static assets (e.g. the button-mapping guide screenshots)
both when running from source and when frozen by PyInstaller. PyInstaller
unpacks ``datas`` into ``sys._MEIPASS`` at runtime; from source the assets live
under ``src/assets``.
"""

import sys
from pathlib import Path

# step_id (selectors.csv) → guide screenshot number. The screenshots illustrate
# where each element sits in the Instagram UI so users can copy its XPath/CSS.
GUIDE_STEP_FOR_SELECTOR: dict[str, int] = {
    "search_icon":   1,
    "search_input":  2,
    "tag_result":    3,
    "post_link":     4,
    "profile_link":  5,
    "username_text": 6,
}


def _assets_root() -> Path:
    """Return the assets directory for both source and frozen (PyInstaller) runs."""
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return Path(base) / "assets"
    # core/assets.py → src/ → src/assets
    return Path(__file__).resolve().parent.parent / "assets"


def guide_image_path(step_no: int) -> Path:
    """Absolute path to ``assets/guide/step{N}.png`` (may not exist)."""
    return _assets_root() / "guide" / f"step{int(step_no)}.png"


def guide_image_for_selector(step_id: str) -> Path | None:
    """Guide screenshot path for a selector ``step_id``, or None if none maps."""
    no = GUIDE_STEP_FOR_SELECTOR.get(step_id)
    if no is None:
        return None
    return guide_image_path(no)
