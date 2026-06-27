from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap


PROJECT_ROOT = Path(__file__).resolve().parent.parent
COMPANY_LOGO_PATH = PROJECT_ROOT / "assets" / "logo.png"
LEGACY_COMPANY_LOGO_PATH = PROJECT_ROOT / "assets" / "images" / "logo.png"


def get_company_logo_path() -> Path:
    """Return permanent corporate logo path with safe legacy fallback."""
    if COMPANY_LOGO_PATH.exists():
        return COMPANY_LOGO_PATH
    if LEGACY_COMPANY_LOGO_PATH.exists():
        return LEGACY_COMPANY_LOGO_PATH
    return COMPANY_LOGO_PATH


def load_company_logo_pixmap() -> QPixmap:
    return QPixmap(str(get_company_logo_path()))


def get_company_logo_icon() -> QIcon:
    return QIcon(str(get_company_logo_path()))


def get_scaled_company_logo(max_width: int, max_height: int) -> QPixmap:
    logo = load_company_logo_pixmap()
    if logo.isNull():
        return logo
    return logo.scaled(
        max(1, max_width),
        max(1, max_height),
        Qt.KeepAspectRatio,
        Qt.SmoothTransformation,
    )


def get_splash_logo_pixmap(max_width: int, max_height: int) -> QPixmap:
    """Future compatible logo loader for splash screens."""
    return get_scaled_company_logo(max_width, max_height)


def get_about_logo_pixmap(max_width: int, max_height: int) -> QPixmap:
    """Future compatible logo loader for about dialogs."""
    return get_scaled_company_logo(max_width, max_height)
