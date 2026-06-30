from __future__ import annotations

import subprocess
from pathlib import Path

from PySide6.QtWidgets import QApplication, QMessageBox


class PdfLocator:
    @staticmethod
    def resolve_path(pdf_path: str) -> str:
        path = str(pdf_path or "").strip()
        if path and Path(path).exists():
            return path
        return ""

    @staticmethod
    def open_folder_and_select(parent, pdf_path: str) -> bool:
        path = PdfLocator.resolve_path(pdf_path)
        if not path:
            QMessageBox.information(parent, "Share", "The PDF file could not be located.")
            return False

        try:
            subprocess.Popen(["explorer", f"/select,{path}"], shell=False)
            return True
        except Exception:
            QMessageBox.information(parent, "Share", "The PDF folder could not be opened right now.")
            return False

    @staticmethod
    def copy_path(parent, pdf_path: str) -> bool:
        path = PdfLocator.resolve_path(pdf_path)
        if not path:
            QMessageBox.information(parent, "Share", "The PDF file could not be located.")
            return False

        clipboard = QApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(path)
        QMessageBox.information(parent, "Share", "PDF path copied successfully.")
        return True
