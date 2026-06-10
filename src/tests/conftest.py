import pytest


@pytest.fixture(scope="session")
def qapp():
    """Shared QApplication for widget construction (pytest-qt 미설치).

    Uses the offscreen platform when available so headless CI/test hosts do
    not need a display. Never starts an event loop — tests call methods
    directly.
    """
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app
