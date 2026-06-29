import os
import tempfile
from typing import Sequence

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QMessageBox

from services.pdf_service import PDFService


class PrintService:
    @staticmethod
    def print_pdf_file(parent, pdf_path: str) -> bool:
        try:
            if os.name == "nt":
                os.startfile(pdf_path, "print")
                return True
            return QDesktopServices.openUrl(QUrl.fromLocalFile(pdf_path))
        except Exception:
            opened = QDesktopServices.openUrl(QUrl.fromLocalFile(pdf_path))
            if opened:
                QMessageBox.information(parent, "Info", "PDF opened. Use your PDF viewer's Print action.")
                return True
            QMessageBox.critical(parent, "Hata", "PDF yazdırılamadı.")
            return False

    @staticmethod
    def print_report(parent, headers: Sequence[str], rows: Sequence[Sequence[object]], title: str, logo_path: str | None = None) -> bool:
        try:
            temp_file = tempfile.NamedTemporaryFile(prefix="mewa_print_", suffix=".pdf", delete=False)
            temp_path = temp_file.name
            temp_file.close()
            ok, err = PDFService.generate_pdf_to_path(
                headers=headers,
                rows=rows,
                save_path=temp_path,
                title=title,
                logo_path=logo_path,
            )
            if not ok:
                QMessageBox.critical(parent, "Hata", f"PDF üretilemedi:\n{err}")
                return False
            return PrintService.print_pdf_file(parent, temp_path)
        except Exception as exc:  # pragma: no cover - defensive fallback
            QMessageBox.critical(parent, "Hata", f"Yazdırma sırasında bir hata oluştu:\n{exc}")
            return False
