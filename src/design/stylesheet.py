"""Generates the application-wide QSS from design tokens."""
from .tokens import Colors as C, Typography as T, Spacing as S, Radius as R


def build() -> str:
    return f"""
/* ── Base ── */
QWidget {{
    background-color: {C.bg};
    color: {C.text};
    font-family: {T.family};
    font-size: {T.size_base}px;
}}
QMainWindow, QDialog {{
    background-color: {C.bg};
}}

/* ── Splitter ── */
QSplitter::handle {{
    background-color: {C.border};
    width: 1px;
}}

/* ── GroupBox ── */
QGroupBox {{
    border: 1px solid {C.border};
    border-radius: {R.lg}px;
    margin-top: {S.sm}px;
    padding: {S.sm}px;
    font-weight: 600;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 {S.xs}px;
    color: {C.muted2};
    font-size: {T.size_small}px;
}}

/* ── Inputs ── */
QLineEdit, QSpinBox, QComboBox {{
    background-color: {C.surface};
    border: 1px solid {C.border};
    border-radius: {R.md}px;
    padding: 6px 10px;
    color: {C.text};
    selection-background-color: {C.accent};
}}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{
    border-color: {C.accent};
}}
QComboBox::drop-down {{
    border: none;
    width: 20px;
}}
QComboBox QAbstractItemView {{
    background-color: {C.surface2};
    border: 1px solid {C.border};
    selection-background-color: {C.accent};
}}

/* ── Buttons ── */
QPushButton {{
    background-color: {C.surface2};
    border: 1px solid {C.border};
    border-radius: {R.md}px;
    padding: 7px 14px;
    color: {C.text};
    font-weight: 500;
}}
QPushButton:hover {{
    background-color: {C.border};
    border-color: {C.accent};
}}
QPushButton:pressed {{
    background-color: {C.accent};
}}
QPushButton:disabled {{
    color: {C.muted};
    border-color: {C.surface2};
}}
QPushButton#btnPrimary {{
    background-color: {C.accent};
    border-color: {C.accent};
    font-weight: 700;
}}
QPushButton#btnPrimary:hover {{
    background-color: {C.accent_light};
    border-color: {C.accent_light};
}}
QPushButton#btnSuccess {{
    background-color: #166534;
    border-color: {C.green};
    color: {C.green};
}}
QPushButton#btnSuccess:hover {{
    background-color: #15803d;
}}
QPushButton#btnDanger {{
    background-color: #7f1d1d;
    border-color: {C.red};
    color: {C.red};
}}

/* ── ProgressBar ── */
QProgressBar {{
    background-color: {C.surface2};
    border: 1px solid {C.border};
    border-radius: {R.sm}px;
    text-align: center;
    color: {C.text};
    height: 18px;
}}
QProgressBar::chunk {{
    background-color: {C.accent};
    border-radius: {R.sm}px;
}}

/* ── TextEdit ── */
QTextEdit {{
    background-color: {C.bg};
    border: 1px solid {C.border};
    border-radius: {R.md}px;
    color: {C.muted2};
    font-family: {T.family_mono};
    font-size: {T.size_small}px;
}}

/* ── Table ── */
QTableWidget {{
    background-color: {C.bg};
    border: 1px solid {C.border};
    border-radius: {R.md}px;
    gridline-color: {C.surface2};
}}
QTableWidget::item {{
    padding: 6px;
    border-bottom: 1px solid {C.surface2};
}}
QTableWidget::item:selected {{
    background-color: {C.surface2};
}}
QHeaderView::section {{
    background-color: {C.surface};
    border: none;
    border-bottom: 1px solid {C.border};
    padding: 6px 8px;
    color: {C.muted2};
    font-size: {T.size_small}px;
    font-weight: 600;
}}

/* ── 결과 테이블(예쁘게) ── */
QTableWidget#resultsTable {{
    background-color: {C.surface};
    alternate-background-color: {C.surface2};
    border: 1px solid {C.border};
    border-radius: {R.lg}px;
}}
QTableWidget#resultsTable::item {{
    padding: 6px 8px;
    border-bottom: 1px solid {C.surface2};
}}
QTableWidget#resultsTable::item:selected {{
    background-color: {C.accent};
    color: {C.text};
}}

/* ── ListWidget ── */
QListWidget {{
    background-color: {C.bg};
    border: 1px solid {C.border};
    border-radius: {R.md}px;
}}
QListWidget::item {{
    padding: {S.xs}px {S.sm}px;
    border-radius: {R.sm}px;
}}
QListWidget::item:selected {{
    background-color: {C.surface2};
}}

/* ── Tabs ── */
QTabWidget::pane {{
    border: 1px solid {C.border};
    border-radius: {R.md}px;
}}
QTabBar::tab {{
    background-color: {C.surface};
    border: 1px solid {C.border};
    border-bottom: none;
    padding: 6px 16px;
    margin-right: 2px;
    border-radius: {R.sm}px {R.sm}px 0 0;
    color: {C.muted2};
}}
QTabBar::tab:selected {{
    background-color: {C.surface2};
    color: {C.text};
    border-bottom: 2px solid {C.accent};
}}

/* ── Scrollbar ── */
QScrollBar:vertical {{
    background-color: {C.bg};
    width: 8px;
    border-radius: {R.sm}px;
}}
QScrollBar::handle:vertical {{
    background-color: {C.border};
    border-radius: {R.sm}px;
    min-height: 20px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}

/* ── Label ── */
QLabel#labelMuted {{
    color: {C.muted2};
    font-size: {T.size_small}px;
}}
QLabel#labelAccent {{
    color: {C.accent_light};
}}

/* ── Button-mapping cards (settings) ── */
QFrame#mappingCard {{
    background-color: {C.surface};
    border: 1px solid {C.border};
    border-radius: {R.lg}px;
}}
QLabel#cardTitle {{
    color: {C.accent_light};
    font-size: {T.size_large}px;
    font-weight: 700;
}}
QLabel#mappingGuide {{
    color: {C.muted2};
    font-size: {T.size_small}px;
}}
QLabel#guideImage {{
    background-color: {C.bg};
    border: 1px solid {C.border};
    border-radius: {R.md}px;
}}
"""
