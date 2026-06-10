"""프로필 상세 다이얼로그 — 캡쳐(왼쪽) + 전체 정보(오른쪽) 가로 배치.

결과 표의 '상세' 버튼으로 연다. 이전/다음 버튼(또는 ←/→ 키)으로 옆 프로필로
넘길 수 있다. 결과 리스트와 현재 인덱스를 받아, 네비게이션 시 내용을 다시 그린다.
"""
from pathlib import Path

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QPixmap, QFont, QDesktopServices
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QWidget, QFrame, QApplication,
)

# (표시 라벨, info 키) — 값이 비면 건너뛴다. URL(프로필 URL)은 텍스트로 보여주지
# 않고 하단의 [URL 복사]/[URL 이동] 버튼으로 다룬다.
_FIELDS: list[tuple[str, str]] = [
    ("유저네임",   "username"),
    ("팔로워",     "followers"),
    ("팔로잉",     "following"),
    ("게시물",     "posts_count"),
    ("소개글",     "bio"),
    ("웹사이트",   "website"),
    ("출처 태그",  "source_tag"),
    ("수집일",     "collected_at"),
]


class ProfileDetailDialog(QDialog):
    def __init__(self, results: list[dict], index: int = 0, parent=None):
        super().__init__(parent)
        self._results = list(results or [])
        n = len(self._results)
        self._index = max(0, min(int(index), n - 1)) if n else 0
        self.setMinimumSize(940, 600)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        self._build_ui()
        self._render()

    # ── UI ──────────────────────────────────────────────────────────────────
    def _build_ui(self):
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # LEFT: 캡쳐 이미지
        left = QFrame()
        left.setObjectName("detailCapture")
        ll = QVBoxLayout(left)
        ll.setContentsMargins(12, 12, 12, 12)
        self._img_label = QLabel("캡쳐 없음")
        self._img_label.setObjectName("labelMuted")
        self._img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._img_label.setMinimumWidth(500)
        ll.addWidget(self._img_label, 1)
        outer.addWidget(left, 3)

        # RIGHT: 헤더(타이틀 + 네비) / 정보 / 닫기
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(16, 14, 16, 14)
        rl.setSpacing(10)

        header = QHBoxLayout()
        self._title = QLabel()
        self._title.setObjectName("labelAccent")
        tf = QFont(); tf.setBold(True); tf.setPointSize(13)
        self._title.setFont(tf)
        header.addWidget(self._title)
        header.addStretch()
        self._btn_prev = QPushButton("◀ 이전")
        self._btn_prev.clicked.connect(self._prev)
        self._btn_next = QPushButton("다음 ▶")
        self._btn_next.clicked.connect(self._next)
        header.addWidget(self._btn_prev)
        header.addWidget(self._btn_next)
        rl.addLayout(header)

        self._pos_label = QLabel()
        self._pos_label.setObjectName("labelMuted")
        rl.addWidget(self._pos_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._info_host = QWidget()
        self._info_layout = QVBoxLayout(self._info_host)
        self._info_layout.setSpacing(8)
        self._info_layout.setContentsMargins(0, 0, 0, 0)
        scroll.setWidget(self._info_host)
        rl.addWidget(scroll, 1)

        footer = QHBoxLayout()
        self._btn_copy = QPushButton("URL 복사")
        self._btn_copy.clicked.connect(self._copy_url)
        self._btn_open = QPushButton("URL 이동")
        self._btn_open.clicked.connect(self._open_url)
        footer.addWidget(self._btn_copy)
        footer.addWidget(self._btn_open)
        footer.addStretch()
        btn_close = QPushButton("닫기")
        btn_close.clicked.connect(self.close)
        footer.addWidget(btn_close)
        rl.addLayout(footer)

        outer.addWidget(right, 2)

    def _current_url(self) -> str:
        if not self._results:
            return ""
        info = self._results[self._index]
        return str(info.get("profile_url") or info.get("website") or "").strip()

    def _copy_url(self):
        url = self._current_url()
        if url:
            QApplication.clipboard().setText(url)
            self._btn_copy.setText("복사됨 ✓")

    def _open_url(self):
        url = self._current_url()
        if url:
            QDesktopServices.openUrl(QUrl(url))

    # ── 렌더링 / 네비게이션 ────────────────────────────────────────────────────
    def _render(self):
        if not self._results:
            self._title.setText("결과 없음")
            self._pos_label.setText("")
            self._btn_prev.setEnabled(False)
            self._btn_next.setEnabled(False)
            self._btn_copy.setEnabled(False)
            self._btn_open.setEnabled(False)
            return
        info = self._results[self._index]
        username = info.get("username", "")
        self.setWindowTitle(f"@{username} — 상세 정보")
        self._title.setText(f"@{username}" if username else "(이름 없음)")
        self._pos_label.setText(f"{self._index + 1} / {len(self._results)}")
        self._btn_prev.setEnabled(self._index > 0)
        self._btn_next.setEnabled(self._index < len(self._results) - 1)

        # URL 버튼: 프로필 URL(없으면 웹사이트)이 있을 때만 활성. 항목 바뀌면 라벨 초기화.
        has_url = bool(self._current_url())
        self._btn_copy.setText("URL 복사")
        self._btn_copy.setEnabled(has_url)
        self._btn_open.setEnabled(has_url)

        # 캡쳐 이미지
        shot = info.get("screenshot_path", "")
        px = QPixmap(shot) if shot and Path(shot).exists() else QPixmap()
        if not px.isNull():
            self._img_label.setPixmap(px.scaled(
                500, 760,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            ))
        else:
            self._img_label.setPixmap(QPixmap())
            self._img_label.setText("캡쳐 없음")

        # 정보 필드 다시 그리기
        self._clear_info()
        for label, key in _FIELDS:
            v = str(info.get(key, "") or "").strip()
            if v:
                self._info_layout.addWidget(self._field_row(label, v))
        self._info_layout.addStretch()

    def _clear_info(self):
        while self._info_layout.count():
            item = self._info_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()

    @staticmethod
    def _field_row(label: str, value: str) -> QWidget:
        row = QWidget()
        h = QHBoxLayout(row)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(12)
        lbl = QLabel(f"<b>{label}</b>")
        lbl.setMinimumWidth(72)
        lbl.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
        val = QLabel(value)
        val.setWordWrap(True)
        val.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        h.addWidget(lbl)
        h.addWidget(val, 1)
        return row

    def _prev(self):
        if self._index > 0:
            self._index -= 1
            self._render()

    def _next(self):
        if self._index < len(self._results) - 1:
            self._index += 1
            self._render()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Left:
            self._prev()
        elif event.key() == Qt.Key.Key_Right:
            self._next()
        else:
            super().keyPressEvent(event)
