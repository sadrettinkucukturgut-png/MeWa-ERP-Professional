from __future__ import annotations

from urllib.parse import quote

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QMessageBox

from services.pdf_locator import PdfLocator


class WhatsAppWebService:
    @staticmethod
    def open_chat(*, parent, phone: str, message: str, pdf_path: str) -> bool:
        encoded = quote(str(message or "").strip())
        web_url = QUrl(f"https://web.whatsapp.com/send?phone={phone}&text={encoded}")
        opened = QDesktopServices.openUrl(web_url)
        if not opened:
            QMessageBox.information(parent, "Share", "WhatsApp Web could not be opened right now.")
            return False

        PdfLocator.open_folder_and_select(parent, pdf_path)
        QMessageBox.information(parent, "Share", "The PDF is ready to attach.")
        return True
