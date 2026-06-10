from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton


class LoginWaitDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Login Required")
        self.setWindowFlags(
            Qt.WindowType.Dialog | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setModal(True)
        self.setMinimumWidth(400)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(28, 28, 28, 28)

        title = QLabel("Instagram Login")
        title.setObjectName("labelAccent")
        layout.addWidget(title)

        msg = QLabel(
            "Chrome has been opened.\n\n"
            "1.  Log in to your Instagram account in the browser.\n"
            "2.  Return to this window.\n"
            "3.  Click  [Login Done]  below."
        )
        msg.setWordWrap(True)
        layout.addWidget(msg)

        btn = QPushButton("Login Done")
        btn.setObjectName("btnSuccess")
        btn.setMinimumHeight(42)
        btn.clicked.connect(self.accept)
        layout.addWidget(btn)
