"""Dependencies 탭 Mixin — requirements.txt pip 설치 실행."""

import sys
from pathlib import Path

from PyQt6.QtCore import QProcess
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QTextEdit


class DepsTabMixin:
    def _build_deps_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(8)

        btn = QPushButton("pip install requirements.txt")
        btn.clicked.connect(self._run_pip)
        layout.addWidget(btn)

        self._pip_log = QTextEdit()
        self._pip_log.setReadOnly(True)
        self._pip_log.setMinimumHeight(120)
        layout.addWidget(self._pip_log)
        layout.addStretch()
        return w

    def _run_pip(self):
        # settings/ 패키지에서 두 단계 위가 src/ → requirements.txt.
        req = str(Path(__file__).parent.parent.parent / "requirements.txt")
        self._pip_log.clear()
        self._process = QProcess(self)
        self._process.readyReadStandardOutput.connect(
            lambda: self._pip_log.append(
                self._process.readAllStandardOutput().data().decode(errors="replace")
            )
        )
        self._process.readyReadStandardError.connect(
            lambda: self._pip_log.append(
                self._process.readAllStandardError().data().decode(errors="replace")
            )
        )
        self._process.start(sys.executable, ["-m", "pip", "install", "-r", req])
