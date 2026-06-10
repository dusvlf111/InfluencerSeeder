"""설정 CSV 폴더/파일(zip) 가져오기·내보내기 Mixin."""

from PyQt6.QtWidgets import QFileDialog, QMessageBox

import core.storage as storage


class ConfigIOMixin:
    def _export_config(self):
        directory = QFileDialog.getExistingDirectory(self, "설정 내보내기 — 폴더 선택")
        if not directory:
            return
        try:
            written = storage.export_config_to_dir(directory)
        except Exception as exc:
            QMessageBox.critical(self, "내보내기 실패", str(exc))
            return
        if written:
            QMessageBox.information(
                self, "설정 내보내기 완료",
                "다음 파일을 내보냈습니다:\n\n" + "\n".join(written),
            )
        else:
            QMessageBox.warning(self, "설정 내보내기", "내보낼 설정 파일이 없습니다.")

    def _export_config_file(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "설정 파일로 내보내기", "influencer-seeder-config.zip",
            "Zip 파일 (*.zip)",
        )
        if not path:
            return
        if not path.lower().endswith(".zip"):
            path += ".zip"
        try:
            written = storage.export_config_to_zip(path)
        except Exception as exc:
            QMessageBox.critical(self, "내보내기 실패", str(exc))
            return
        if written:
            QMessageBox.information(
                self, "설정 내보내기 완료",
                f"{path}\n\n다음 파일을 묶었습니다:\n\n" + "\n".join(written),
            )
        else:
            QMessageBox.warning(self, "설정 내보내기", "내보낼 설정 파일이 없습니다.")

    def _import_config_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "설정 파일에서 불러오기", "", "Zip 파일 (*.zip)",
        )
        if not path:
            return
        try:
            imported = storage.import_config_from_zip(path)
        except Exception as exc:
            QMessageBox.critical(self, "불러오기 실패", str(exc))
            return
        if imported:
            self.load()
            self.imported.emit()
            QMessageBox.information(
                self, "설정 불러오기 완료",
                "다음 파일을 반영했습니다:\n\n" + "\n".join(imported),
            )
        else:
            QMessageBox.warning(
                self, "설정 불러오기",
                "선택한 파일에서 인식 가능한 설정 CSV 를 찾지 못했습니다.",
            )

    def _import_config(self):
        directory = QFileDialog.getExistingDirectory(self, "설정 불러오기 — 폴더 선택")
        if not directory:
            return
        try:
            imported = storage.import_config_from_dir(directory)
        except Exception as exc:
            QMessageBox.critical(self, "불러오기 실패", str(exc))
            return
        if imported:
            self.load()              # 반영된 CSV 로 UI 갱신
            self.imported.emit()     # 메인뷰 재로딩 신호
            QMessageBox.information(
                self, "설정 불러오기 완료",
                "다음 파일을 반영했습니다:\n\n" + "\n".join(imported),
            )
        else:
            QMessageBox.warning(
                self, "설정 불러오기",
                "선택한 폴더에서 인식 가능한 설정 CSV 를 찾지 못했습니다.",
            )
