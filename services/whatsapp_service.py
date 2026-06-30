from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Callable, Optional
from urllib.parse import quote

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from ui.new_cari_dialog import NewCariDialog
from services.whatsapp_desktop_service import WhatsAppDesktopService


class EnterNumberOnceDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Enter Number Once")
        self.number = ""

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Number:"))

        row = QHBoxLayout()
        row.addWidget(QLabel("+"))
        self.number_input = QLineEdit()
        self.number_input.setPlaceholderText("90 ___________")
        row.addWidget(self.number_input)
        layout.addLayout(row)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        ok_btn = QPushButton("Use")
        cancel_btn = QPushButton("Cancel")
        ok_btn.clicked.connect(self._accept)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(ok_btn)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

    def _accept(self):
        value = str(self.number_input.text() or "").strip()
        if not value:
            QMessageBox.warning(self, "Warning", "Please enter a number.")
            return
        self.number = value
        self.accept()


class WhatsAppService:
    @staticmethod
    def _db_path() -> Path:
        return Path(__file__).resolve().parent.parent / "database" / "mewa.db"

    @staticmethod
    def normalize_phone(phone: str) -> str:
        cleaned = "".join(ch for ch in str(phone or "") if ch.isdigit() or ch == "+")
        if cleaned.startswith("+"):
            cleaned = cleaned[1:]
        if cleaned.startswith("00"):
            cleaned = cleaned[2:]
        if cleaned.startswith("0") and len(cleaned) == 11:
            cleaned = "90" + cleaned[1:]
        elif len(cleaned) == 10:
            cleaned = "90" + cleaned
        return cleaned if len(cleaned) >= 10 else ""

    @classmethod
    def _resolve_customer_numbers(cls, customer_code: str, customer_name: str) -> dict[str, str]:
        db_path = cls._db_path()
        if not db_path.exists():
            return {"whatsapp": "", "mobile": "", "phone": ""}

        with sqlite3.connect(str(db_path)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("PRAGMA table_info(cariler)")
            cols = {str(row[1]).lower() for row in cursor.fetchall()}
            has_mobile = "mobile" in cols
            has_whatsapp = "whatsapp" in cols

            mobile_expr = "COALESCE(mobile, '')" if has_mobile else "''"
            whatsapp_expr = "COALESCE(whatsapp, '')" if has_whatsapp else "''"

            query = f"""
                SELECT
                    {whatsapp_expr} AS whatsapp,
                    {mobile_expr} AS mobile,
                    COALESCE(telefon, '') AS phone
                FROM cariler
                WHERE LOWER(COALESCE(cari_kodu, '')) = LOWER(?)
                LIMIT 1
            """

            if customer_code:
                cursor.execute(query, (customer_code,))
                row = cursor.fetchone()
                if row is not None:
                    return {
                        "whatsapp": str(row["whatsapp"] or "").strip(),
                        "mobile": str(row["mobile"] or "").strip(),
                        "phone": str(row["phone"] or "").strip(),
                    }

            if customer_name:
                query = f"""
                    SELECT
                        {whatsapp_expr} AS whatsapp,
                        {mobile_expr} AS mobile,
                        COALESCE(telefon, '') AS phone
                    FROM cariler
                    WHERE LOWER(COALESCE(firma_unvani, '')) = LOWER(?)
                    LIMIT 1
                """
                cursor.execute(query, (customer_name,))
                row = cursor.fetchone()
                if row is not None:
                    return {
                        "whatsapp": str(row["whatsapp"] or "").strip(),
                        "mobile": str(row["mobile"] or "").strip(),
                        "phone": str(row["phone"] or "").strip(),
                    }

        return {"whatsapp": "", "mobile": "", "phone": ""}

    @classmethod
    def _resolve_customer_code_by_name(cls, customer_name: str) -> str:
        name = str(customer_name or "").strip()
        if not name:
            return ""
        db_path = cls._db_path()
        if not db_path.exists():
            return ""

        with sqlite3.connect(str(db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT COALESCE(cari_kodu, '')
                FROM cariler
                WHERE LOWER(COALESCE(firma_unvani, '')) = LOWER(?)
                LIMIT 1
                """,
                (name,),
            )
            row = cursor.fetchone()
            if row is None:
                return ""
            return str(row[0] or "").strip()

    @classmethod
    def _choose_number(
        cls,
        *,
        preferred_whatsapp: str,
        preferred_mobile: str,
        preferred_phone: str,
        db_numbers: dict[str, str],
    ) -> str:
        candidates = [
            preferred_whatsapp,
            db_numbers.get("whatsapp", ""),
            preferred_mobile,
            db_numbers.get("mobile", ""),
            preferred_phone,
            db_numbers.get("phone", ""),
        ]
        for number in candidates:
            normalized = cls.normalize_phone(number)
            if normalized:
                return normalized
        return ""

    @staticmethod
    def _open_customer_card(parent, customer_code: str):
        dialog = NewCariDialog(cari_kodu=customer_code, parent=parent, focus_field="whatsapp")
        dialog.exec()

    @staticmethod
    def _ask_missing_number_action(parent) -> str:
        box = QMessageBox(parent)
        box.setIcon(QMessageBox.Information)
        box.setWindowTitle("WhatsApp")
        box.setText(
            "No WhatsApp or phone number was found for this customer.\n\n"
            "Would you like to enter one now?"
        )

        btn_open = box.addButton("Open Customer Card", QMessageBox.ActionRole)
        btn_once = box.addButton("Enter Number Once", QMessageBox.ActionRole)
        btn_cancel = box.addButton("Cancel", QMessageBox.RejectRole)
        box.exec()

        clicked = box.clickedButton()
        if clicked == btn_open:
            return "open-card"
        if clicked == btn_once:
            return "enter-once"
        if clicked == btn_cancel:
            return "cancel"
        return "cancel"

    @classmethod
    def resolve_contact_number_with_prompt(
        cls,
        *,
        parent,
        customer_code: str,
        customer_name: str,
        preferred_whatsapp: str,
        preferred_mobile: str = "",
        preferred_phone: str = "",
    ) -> str:
        db_numbers = cls._resolve_customer_numbers(customer_code=customer_code, customer_name=customer_name)
        number = cls._choose_number(
            preferred_whatsapp=preferred_whatsapp,
            preferred_mobile=preferred_mobile,
            preferred_phone=preferred_phone,
            db_numbers=db_numbers,
        )
        if number:
            return number

        action = cls._ask_missing_number_action(parent)
        if action == "open-card":
            resolved_code = str(customer_code or "").strip() or cls._resolve_customer_code_by_name(customer_name)
            if resolved_code:
                cls._open_customer_card(parent, resolved_code)
            else:
                QMessageBox.information(parent, "Info", "Customer card can be opened only when customer code is available.")
            return ""

        if action == "enter-once":
            once = EnterNumberOnceDialog(parent)
            if not once.exec() or not once.number:
                return ""
            return cls.normalize_phone(once.number)

        return ""

    @classmethod
    def send_document(
        cls,
        *,
        parent,
        customer_code: str,
        customer_name: str,
        message: str,
        ensure_pdf_path: Callable[[], Optional[str]],
        preferred_whatsapp: str = "",
        preferred_mobile: str = "",
        preferred_phone: str = "",
    ) -> bool:
        phone = cls.resolve_contact_number_with_prompt(
            parent=parent,
            customer_code=customer_code,
            customer_name=customer_name,
            preferred_whatsapp=preferred_whatsapp,
            preferred_mobile=preferred_mobile,
            preferred_phone=preferred_phone,
        )
        if not phone:
            return False

        pdf_path = ensure_pdf_path()
        if not pdf_path:
            QMessageBox.information(parent, "WhatsApp", "The document PDF could not be prepared right now.")
            return False

        if WhatsAppDesktopService.is_installed():
            return WhatsAppDesktopService.send_with_attachment_preferred(
                parent=parent,
                phone=phone,
                message=message,
                pdf_path=str(pdf_path),
            )

        message_text = quote(str(message or "").strip())
        web_url = QUrl(f"https://web.whatsapp.com/send?phone={phone}&text={message_text}")
        opened = QDesktopServices.openUrl(web_url)
        if not opened:
            QMessageBox.information(parent, "WhatsApp", "WhatsApp could not be opened right now.")
            return False

        clipboard = QApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(str(pdf_path))

        QMessageBox.information(
            parent,
            "Info",
            "PDF has been generated.\n\n"
            "Please attach it to the WhatsApp conversation.",
        )
        return True
