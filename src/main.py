import sys
from PyQt6.QtWidgets import QApplication

from design.stylesheet import build as build_stylesheet
from ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("인플루언서 시딩기")
    app.setStyleSheet(build_stylesheet())
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
