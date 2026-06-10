from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton


class LoginWaitDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("인스타그램 로그인")
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

        title = QLabel("인스타그램 로그인")
        title.setObjectName("labelAccent")
        layout.addWidget(title)

        msg = QLabel(
            "브라우저(Chrome)가 열렸습니다.\n\n"
            "1.  브라우저에서 인스타그램에 로그인하세요.\n"
            "2.  이 창으로 돌아오세요.\n"
            "3.  아래 [로그인 완료] 버튼을 누르세요."
        )
        msg.setWordWrap(True)
        layout.addWidget(msg)

        btn = QPushButton("로그인 완료")
        btn.setObjectName("btnSuccess")
        btn.setMinimumHeight(42)
        btn.clicked.connect(self.accept)
        layout.addWidget(btn)
