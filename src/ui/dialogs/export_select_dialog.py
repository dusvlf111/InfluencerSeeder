"""내보내기 항목 선택 다이얼로그 (Fix-2 D).

``SHAREABLE_FILES`` 각 항목을 체크박스로 보여주고(라벨=``SHAREABLE_LABELS``),
사용자가 zip 에 담을 파일을 고른다. 존재하지 않는 파일(예: 아직 수집 전 results.csv)
은 회색·해제 상태로 표시한다. ``selected_names()`` 가 선택된 파일명 리스트를 반환한다.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QCheckBox,
)

import core.storage as storage


class ExportSelectDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("내보낼 항목 선택")
        self.setObjectName("exportSelectDialog")
        self.setModal(True)
        self.setMinimumWidth(360)
        self._checks: dict[str, QCheckBox] = {}
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(24, 24, 24, 24)

        title = QLabel("내보낼 항목 선택")
        title.setObjectName("labelAccent")
        layout.addWidget(title)

        note = QLabel("zip 파일에 담을 항목을 선택하세요. 존재하지 않는 항목은 선택할 수 없습니다.")
        note.setObjectName("labelMuted")
        note.setWordWrap(True)
        layout.addWidget(note)

        for name in storage.SHAREABLE_FILES:
            label = storage.SHAREABLE_LABELS.get(name, name)
            chk = QCheckBox(f"{label}  ({name})")
            exists = storage._path(name).exists()
            chk.setChecked(exists)
            chk.setEnabled(exists)
            if not exists:
                chk.setToolTip("아직 생성되지 않은 파일입니다.")
            self._checks[name] = chk
            layout.addWidget(chk)

        # 전체선택 / 전체해제
        sel_row = QHBoxLayout()
        btn_all = QPushButton("전체선택")
        btn_all.clicked.connect(lambda: self._set_all(True))
        btn_none = QPushButton("전체해제")
        btn_none.clicked.connect(lambda: self._set_all(False))
        sel_row.addWidget(btn_all)
        sel_row.addWidget(btn_none)
        sel_row.addStretch()
        layout.addLayout(sel_row)

        # 내보내기 / 취소
        act_row = QHBoxLayout()
        act_row.addStretch()
        btn_cancel = QPushButton("취소")
        btn_cancel.clicked.connect(self.reject)
        btn_export = QPushButton("내보내기")
        btn_export.setObjectName("btnPrimary")
        btn_export.clicked.connect(self.accept)
        act_row.addWidget(btn_cancel)
        act_row.addWidget(btn_export)
        layout.addLayout(act_row)

    def _set_all(self, checked: bool):
        for chk in self._checks.values():
            if chk.isEnabled():
                chk.setChecked(checked)

    def selected_names(self) -> list[str]:
        """Shareable filenames whose checkbox is checked (stable order)."""
        return [
            name for name in storage.SHAREABLE_FILES
            if self._checks[name].isChecked()
        ]
