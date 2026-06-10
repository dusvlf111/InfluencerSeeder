"""프로필 상세 정보 다이얼로그 — 호버 시 프로필 캡처 + 전체 필드 표시."""
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QWidget, QFrame,
)


class ProfileDetailDialog(QDialog):
    def __init__(self, info: dict, parent=None):
        super().__init__(parent)
        username = info.get("username", "")
        self.setWindowTitle(f"@{username} — 상세 정보")
        self.setMinimumWidth(580)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setWindowFlags(
            self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint
        )
        self._build_ui(info)

    def _build_ui(self, info: dict):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 12)
        root.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setSpacing(10)
        layout.setContentsMargins(16, 16, 16, 16)

        # 프로필 캡처 이미지
        shot_path = info.get("screenshot_path", "")
        if shot_path and Path(shot_path).exists():
            px = QPixmap(shot_path)
            if not px.isNull():
                img_label = QLabel()
                scaled = px.scaled(
                    548, 420,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                img_label.setPixmap(scaled)
                img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                layout.addWidget(img_label)
                sep = QFrame()
                sep.setFrameShape(QFrame.Shape.HLine)
                sep.setFrameShadow(QFrame.Shadow.Sunken)
                layout.addWidget(sep)

        # 정보 필드
        fields = [
            ("유저네임",   info.get("username", "")),
            ("팔로워",     info.get("followers", "")),
            ("팔로잉",     info.get("following", "")),
            ("게시물",     info.get("posts_count", "")),
            ("소개글",     info.get("bio", "")),
            ("웹사이트",   info.get("website", "")),
            ("프로필 URL", info.get("profile_url", "")),
            ("출처 태그",  info.get("source_tag", "")),
            ("수집일",     info.get("collected_at", "")),
        ]
        for label, value in fields:
            v = str(value).strip()
            if not v:
                continue
            row = QHBoxLayout()
            row.setSpacing(12)
            lbl = QLabel(f"<b>{label}</b>")
            lbl.setMinimumWidth(80)
            lbl.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
            val = QLabel(v)
            val.setWordWrap(True)
            val.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            row.addWidget(lbl)
            row.addWidget(val, 1)
            layout.addLayout(row)

        layout.addStretch()
        scroll.setWidget(content)
        root.addWidget(scroll)

        btn_close = QPushButton("닫기")
        btn_close.clicked.connect(self.close)
        root.addWidget(btn_close, alignment=Qt.AlignmentFlag.AlignRight)
        # 여백
        root.setContentsMargins(0, 0, 12, 12)
