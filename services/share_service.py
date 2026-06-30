from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QMessageBox

from services.email_service import EmailService
from services.pdf_locator import PdfLocator
from services.whatsapp_desktop_service import WhatsAppDesktopService
from services.whatsapp_service import WhatsAppService
from services.whatsapp_web_service import WhatsAppWebService


class ShareMethod:
    WHATSAPP_DESKTOP = "whatsapp_desktop"
    WHATSAPP_WEB = "whatsapp_web"
    EMAIL = "email"
    OPEN_FOLDER = "open_folder"
    COPY_PDF_PATH = "copy_pdf_path"


@dataclass
class ShareContext:
    document_type: str
    document_number: str
    customer_code: str
    customer_name: str
    customer_email: str
    preferred_whatsapp: str
    message: str
    ensure_pdf_path: Callable[[], Optional[str]]


class ShareService:
    SETTINGS_ORG = "MeWa"
    SETTINGS_APP = "ERP"
    KEY_DEFAULT_METHOD = "share/default_method"
    KEY_REMEMBER_DEFAULT = "share/remember_default"

    @staticmethod
    def available_default_methods() -> list[tuple[str, str]]:
        return [
            ("WhatsApp Desktop", ShareMethod.WHATSAPP_DESKTOP),
            ("WhatsApp Web", ShareMethod.WHATSAPP_WEB),
            ("Email", ShareMethod.EMAIL),
            ("Open Folder", ShareMethod.OPEN_FOLDER),
            ("Copy PDF Path", ShareMethod.COPY_PDF_PATH),
        ]

    @classmethod
    def _settings(cls) -> QSettings:
        return QSettings(cls.SETTINGS_ORG, cls.SETTINGS_APP)

    @classmethod
    def get_default_method(cls) -> str:
        settings = cls._settings()
        value = str(settings.value(cls.KEY_DEFAULT_METHOD, ShareMethod.WHATSAPP_DESKTOP) or ShareMethod.WHATSAPP_DESKTOP)
        return value

    @classmethod
    def set_default_method(cls, method: str) -> None:
        cls._settings().setValue(cls.KEY_DEFAULT_METHOD, method)

    @classmethod
    def is_remember_default_enabled(cls) -> bool:
        value = cls._settings().value(cls.KEY_REMEMBER_DEFAULT, False)
        return str(value).lower() in {"1", "true", "yes"}

    @classmethod
    def set_remember_default_enabled(cls, enabled: bool) -> None:
        cls._settings().setValue(cls.KEY_REMEMBER_DEFAULT, bool(enabled))

    @classmethod
    def _ensure_pdf(cls, parent, ensure_pdf_path: Callable[[], Optional[str]]) -> str:
        path = str(ensure_pdf_path() or "").strip()
        if not path:
            QMessageBox.information(parent, "Share", "The PDF could not be prepared right now.")
            return ""
        return path

    @classmethod
    def execute(cls, *, parent, method: str, context: ShareContext) -> bool:
        method_value = str(method or "").strip()

        if method_value in (ShareMethod.WHATSAPP_DESKTOP, ShareMethod.WHATSAPP_WEB):
            phone = WhatsAppService.resolve_contact_number_with_prompt(
                parent=parent,
                customer_code=context.customer_code,
                customer_name=context.customer_name,
                preferred_whatsapp=context.preferred_whatsapp,
            )
            if not phone:
                return False

            pdf_path = cls._ensure_pdf(parent, context.ensure_pdf_path)
            if not pdf_path:
                return False

            if method_value == ShareMethod.WHATSAPP_DESKTOP:
                if WhatsAppDesktopService.is_installed():
                    return WhatsAppDesktopService.send_with_attachment_preferred(
                        parent=parent,
                        phone=phone,
                        message=context.message,
                        pdf_path=pdf_path,
                    )
                return WhatsAppWebService.open_chat(
                    parent=parent,
                    phone=phone,
                    message=context.message,
                    pdf_path=pdf_path,
                )

            return WhatsAppWebService.open_chat(
                parent=parent,
                phone=phone,
                message=context.message,
                pdf_path=pdf_path,
            )

        if method_value == ShareMethod.EMAIL:
            pdf_path = cls._ensure_pdf(parent, context.ensure_pdf_path)
            if not pdf_path:
                return False
            recipient = str(context.customer_email or "").strip()
            subject = f"{context.document_type} - {context.document_number}".strip(" -")
            body = context.message
            return EmailService.send_with_pdf(
                parent=parent,
                recipient=recipient,
                subject=subject,
                body=body,
                pdf_path=pdf_path,
            )

        if method_value == ShareMethod.OPEN_FOLDER:
            pdf_path = cls._ensure_pdf(parent, context.ensure_pdf_path)
            if not pdf_path:
                return False
            return PdfLocator.open_folder_and_select(parent, pdf_path)

        if method_value == ShareMethod.COPY_PDF_PATH:
            pdf_path = cls._ensure_pdf(parent, context.ensure_pdf_path)
            if not pdf_path:
                return False
            return PdfLocator.copy_path(parent, pdf_path)

        QMessageBox.information(parent, "Share", "Selected sharing method is not available.")
        return False
