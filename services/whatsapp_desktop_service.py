from __future__ import annotations

import os
import subprocess
from pathlib import Path
from urllib.parse import quote

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QMessageBox

try:
    import winreg  # type: ignore
except Exception:  # pragma: no cover
    winreg = None


class WhatsAppDesktopService:
    @staticmethod
    def _candidate_paths() -> list[Path]:
        local_app = Path(os.environ.get("LOCALAPPDATA", ""))
        program_files = Path(os.environ.get("ProgramFiles", "C:\\Program Files"))
        program_files_x86 = Path(os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)"))

        return [
            local_app / "WhatsApp" / "WhatsApp.exe",
            program_files / "WindowsApps" / "5319275A.WhatsAppDesktop*",
            program_files / "WhatsApp" / "WhatsApp.exe",
            program_files_x86 / "WhatsApp" / "WhatsApp.exe",
        ]

    @classmethod
    def _find_executable(cls) -> str:
        for candidate in cls._candidate_paths():
            if "*" in str(candidate):
                continue
            if candidate.exists() and candidate.is_file():
                return str(candidate)
        return ""

    @staticmethod
    def _is_protocol_registered() -> bool:
        if winreg is None:
            return False
        try:
            with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, r"whatsapp\\shell\\open\\command"):
                return True
        except Exception:
            return False

    @classmethod
    def is_installed(cls) -> bool:
        return bool(cls._find_executable() or cls._is_protocol_registered())

    @classmethod
    def _open_chat_uri(cls, phone: str, message: str) -> bool:
        encoded = quote(str(message or "").strip())
        url = QUrl(f"whatsapp://send?phone={phone}&text={encoded}")
        return QDesktopServices.openUrl(url)

    @classmethod
    def _launch_app(cls) -> bool:
        executable = cls._find_executable()
        if not executable:
            return False
        try:
            subprocess.Popen([executable], shell=False)
            return True
        except Exception:
            return False

    @staticmethod
    def _open_and_select_pdf(pdf_path: str) -> bool:
        path = str(pdf_path or "").strip()
        if not path or not Path(path).exists():
            return False
        try:
            subprocess.Popen(["explorer", f"/select,{path}"], shell=False)
            return True
        except Exception:
            return False

    @classmethod
    def send_with_attachment_preferred(
        cls,
        *,
        parent,
        phone: str,
        message: str,
        pdf_path: str,
    ) -> bool:
        if not cls.is_installed():
            return False

        opened_chat = cls._open_chat_uri(phone, message)
        if not opened_chat:
            cls._launch_app()
            opened_chat = cls._open_chat_uri(phone, message)

        cls._open_and_select_pdf(pdf_path)

        if opened_chat:
            QMessageBox.information(
                parent,
                "WhatsApp",
                "WhatsApp Desktop has been opened and message is prepared.\n\n"
                "The generated PDF has been selected in Explorer.\n"
                "Please attach it to the conversation and press Send.",
            )
            return True

        QMessageBox.information(
            parent,
            "WhatsApp",
            "WhatsApp Desktop is installed, but chat automation is limited on this Windows setup.\n\n"
            "The generated PDF has been prepared and selected in Explorer.\n"
            "Please open WhatsApp Desktop, choose the customer chat, attach the file, and press Send.",
        )
        return True
