"""설정·데이터 공유 Mixin (Fix-2 D) — zip 전용 내보내기/불러오기.

내보내기: ``ExportSelectDialog`` 로 항목을 체크 선택 → zip 저장.
불러오기: zip 선택 → 압축 풀고 자동 적용(``self.load()`` + ``imported`` 신호).
설정 CSV들 + 제외명단(excluded.csv) + 수집데이터(results.csv) + 수집항목(fields.csv)
을 하나의 zip 으로 주고받는다.
"""

from PyQt6.QtWidgets import QFileDialog, QMessageBox, QDialog

import core.storage as storage
from ui.dialogs.export_select_dialog import ExportSelectDialog


class ConfigIOMixin:
    def _export_config(self):
        dlg = ExportSelectDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        names = dlg.selected_names()
        if not names:
            QMessageBox.warning(self, "내보내기", "선택한 항목이 없습니다.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "설정·데이터 내보내기", "influencer-seeder-export.zip",
            "Zip 파일 (*.zip)",
        )
        if not path:
            return
        if not path.lower().endswith(".zip"):
            path += ".zip"
        try:
            written = storage.export_config_to_zip(path, names=names)
        except Exception as exc:
            QMessageBox.critical(self, "내보내기 실패", str(exc))
            return
        if written:
            labels = [storage.SHAREABLE_LABELS.get(n, n) for n in written]
            QMessageBox.information(
                self, "내보내기 완료",
                f"{path}\n\n다음 항목을 묶었습니다:\n\n" + "\n".join(labels),
            )
        else:
            QMessageBox.warning(self, "내보내기", "내보낼 파일이 없습니다.")

    def _import_config(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "설정·데이터 불러오기", "", "Zip 파일 (*.zip)",
        )
        if not path:
            return
        try:
            imported = storage.import_config_from_zip(path)
        except Exception as exc:
            QMessageBox.critical(self, "불러오기 실패", str(exc))
            return
        if imported:
            self.load()              # 반영된 CSV 로 UI 갱신
            self.imported.emit()     # 메인뷰 재로딩 신호
            labels = [storage.SHAREABLE_LABELS.get(n, n) for n in imported]
            QMessageBox.information(
                self, "불러오기 완료",
                "다음 항목을 반영했습니다:\n\n" + "\n".join(labels),
            )
        else:
            QMessageBox.warning(
                self, "불러오기",
                "선택한 파일에서 인식 가능한 설정/데이터 CSV 를 찾지 못했습니다.",
            )
