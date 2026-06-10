"""수집 항목 탭 Mixin (Fix-2 B) — 어떤 프로필 필드를 수집/저장할지 토글.

``username`` 은 항상 수집(체크 고정·disabled). 나머지 필드는 체크박스로 켜고 끈다.
저장은 storage.save_fields(dict[str,bool]), 로드는 storage.load_fields().
"""

from PyQt6.QtWidgets import QWidget, QFormLayout, QCheckBox, QLabel

import core.storage as storage

# field → 한국어 라벨 (수집 가능한 필드 순서).
_FIELD_LABELS: list[tuple[str, str]] = [
    ("full_name",   "이름"),
    ("followers",   "팔로워"),
    ("following",   "팔로잉"),
    ("posts_count", "게시물 수"),
    ("bio",         "소개"),
    ("website",     "웹사이트"),
    ("is_private",  "비공개 여부"),
]


class FieldsTabMixin:
    def _build_fields_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setSpacing(12)
        form.setContentsMargins(28, 20, 28, 20)

        note = QLabel("수집/저장할 프로필 항목을 선택하세요. 체크 해제한 항목은 빈 칸으로 저장됩니다.")
        note.setObjectName("labelMuted")
        note.setWordWrap(True)
        form.addRow(note)

        # username 은 항상 수집 — 비활성 표시.
        always = QCheckBox("아이디(username) — 항상 수집")
        always.setChecked(True)
        always.setEnabled(False)
        form.addRow("필수", always)
        self._cf_username = always

        # 토글 가능한 필드들.
        self._field_checks: dict[str, QCheckBox] = {}
        for field, label in _FIELD_LABELS:
            chk = QCheckBox(label)
            chk.setChecked(True)
            setattr(self, f"_cf_{field}", chk)
            self._field_checks[field] = chk
            form.addRow(label, chk)

        return w

    def _populate_fields(self, fields: dict):
        for field, chk in self._field_checks.items():
            chk.setChecked(bool(fields.get(field, True)))

    def _collect_fields_settings(self) -> dict:
        return {field: chk.isChecked() for field, chk in self._field_checks.items()}
