from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap


PROJECT_ROOT = Path(__file__).resolve().parent.parent
COMPANY_LOGO_PATH = PROJECT_ROOT / "assets" / "logo.png"
LEGACY_COMPANY_LOGO_PATH = PROJECT_ROOT / "assets" / "images" / "logo.png"
BRANDING_DIR = PROJECT_ROOT / "assets" / "branding"
TEMPLATES_DIR = PROJECT_ROOT / "assets" / "templates"


_BRANDING_FILES = {
    "company_logo": "company_logo.png",
    "company_logo_dark": "company_logo_dark.png",
    "company_signature": "company_signature.png",
    "company_stamp": "company_stamp.png",
    "watermark": "watermark.png",
}

_TEMPLATE_FILES = {
    "PROFORMA": "proforma_background.png",
    "EXPORT_SALES_INVOICE": "export_invoice_background.png",
    "COMMERCIAL_INVOICE": "commercial_invoice_background.png",
    "PACKING_LIST": "packing_list_background.png",
    "PURCHASE_INVOICE": "purchase_invoice_background.png",
}


def get_company_logo_path() -> Path:
    """Return permanent corporate logo path with safe legacy fallback."""
    try:
        from models.company_profile_model import CompanyProfileModel

        profile = CompanyProfileModel.get_profile()
        dynamic_logo = CompanyProfileModel.resolve_path(str(profile.get("logo_path") or ""))
        if dynamic_logo and dynamic_logo.exists():
            return dynamic_logo
    except Exception:
        pass

    preferred = get_branding_asset_path("company_logo")
    if preferred.exists():
        return preferred
    if COMPANY_LOGO_PATH.exists():
        return COMPANY_LOGO_PATH
    if LEGACY_COMPANY_LOGO_PATH.exists():
        return LEGACY_COMPANY_LOGO_PATH
    return COMPANY_LOGO_PATH


def get_branding_asset_path(asset_key: str) -> Path:
    normalized_key = str(asset_key or "").strip().lower()
    try:
        from models.company_profile_model import CompanyProfileModel

        profile = CompanyProfileModel.get_profile()
        if normalized_key == "company_logo":
            dynamic = CompanyProfileModel.resolve_path(str(profile.get("logo_path") or ""))
            if dynamic and dynamic.exists():
                return dynamic
        elif normalized_key == "company_signature":
            dynamic = CompanyProfileModel.resolve_path(str(profile.get("signature_path") or ""))
            if dynamic and dynamic.exists():
                return dynamic
        elif normalized_key == "company_stamp":
            dynamic = CompanyProfileModel.resolve_path(str(profile.get("stamp_path") or ""))
            if dynamic and dynamic.exists():
                return dynamic
    except Exception:
        pass

    filename = _BRANDING_FILES.get(normalized_key, "")
    if filename:
        return BRANDING_DIR / filename
    return BRANDING_DIR / str(asset_key or "")


def get_document_template_background_path(document_kind: str) -> Path:
    key = str(document_kind or "").strip().upper()
    filename = _TEMPLATE_FILES.get(key, "")
    if filename:
        return TEMPLATES_DIR / filename
    return TEMPLATES_DIR / ""


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
