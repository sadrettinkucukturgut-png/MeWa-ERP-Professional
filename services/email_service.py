from __future__ import annotations

from urllib.parse import quote

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QMessageBox

from services.pdf_locator import PdfLocator


class EmailService:
    @staticmethod
    def send_with_pdf(
        *,
        parent,
        recipient: str,
        subject: str,
        body: str,
        pdf_path: str,
    ) -> bool:
        mailto = f"mailto:{recipient}?subject={quote(subject)}&body={quote(body)}"
        opened = QDesktopServices.openUrl(QUrl(mailto))
        if not opened:
            QMessageBox.information(parent, "Share", "Default email client could not be opened.")
            return False

        PdfLocator.copy_path(parent, pdf_path)
        QMessageBox.information(
            parent,
            "Share",
            "Email client opened. Please attach the generated PDF.",
        )
        return True
