import os
import re
import sqlite3
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable, Optional

from PySide6.QtCore import QRect, QRectF, QSize, Qt, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QFont, QIcon, QPageLayout, QPageSize, QPainter, QPen, QPdfWriter, QPixmap
from PySide6.QtPrintSupport import QPrintDialog, QPrinter, QPrintPreviewWidget
from PySide6.QtWidgets import QFileDialog, QLabel, QMainWindow, QMenu, QMessageBox, QToolBar
from PySide6.QtWidgets import QToolButton, QWidgetAction
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image as RLImage
from reportlab.platypus import KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

try:
    from PySide6.QtPdf import QPdfDocument
    from PySide6.QtPdfWidgets import QPdfView
except Exception:  # pragma: no cover - optional QtPdf module
    QPdfDocument = None
    QPdfView = None

from services.excel_service import ExcelService
from services.share_service import ShareContext, ShareMethod, ShareService
from shared.app_assets import get_branding_asset_path, get_company_logo_path, get_document_template_background_path

DEFAULT_MESSAGE_NEVER_SAVED = "This document must be saved before preview."
DEFAULT_MESSAGE_UNSAVED = "This document has changed.\n\nDo you want to save before opening the preview?"
DEFAULT_WHATSAPP_MESSAGE = (
    "Dear Customer,\n\n"
    "Please find attached your document.\n\n"
    "Best Regards\n"
    "MeWa Automotive"
)


def _preferred_branding_asset(*filenames: str) -> Path:
    branding_dir = Path(__file__).resolve().parent.parent / "assets" / "branding"
    for filename in filenames:
        candidate = branding_dir / filename
        if candidate.exists():
            return candidate
    return branding_dir / filenames[0]


def _packing_list_template_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "templates" / "packing_list"


def _packing_list_background_path() -> Path:
    template_dir = _packing_list_template_dir()
    for filename in ("background.png", "packing_list_background.png", "template.png"):
        candidate = template_dir / filename
        if candidate.exists():
            return candidate
    fallback = get_document_template_background_path("PACKING_LIST")
    return fallback if fallback.exists() else template_dir / "background.png"


def _resolve_unicode_fonts() -> tuple[str, str]:
    regular_name = "MeWaUnicode"
    bold_name = "MeWaUnicodeBold"
    registered = set(pdfmetrics.getRegisteredFontNames())
    if regular_name in registered and bold_name in registered:
        return regular_name, bold_name

    branding_font_dir = Path(__file__).resolve().parent.parent / "assets" / "branding" / "fonts"
    windows_font_dir = Path(os.environ.get("WINDIR", "C:\\Windows")) / "Fonts"

    candidates = [
        (branding_font_dir / "DejaVuSans.ttf", branding_font_dir / "DejaVuSans-Bold.ttf"),
        (branding_font_dir / "NotoSans-Regular.ttf", branding_font_dir / "NotoSans-Bold.ttf"),
        (windows_font_dir / "DejaVuSans.ttf", windows_font_dir / "DejaVuSans-Bold.ttf"),
        (windows_font_dir / "NotoSans-Regular.ttf", windows_font_dir / "NotoSans-Bold.ttf"),
        (windows_font_dir / "arial.ttf", windows_font_dir / "arialbd.ttf"),
    ]

    for regular_path, bold_path in candidates:
        if regular_path.exists() and bold_path.exists():
            pdfmetrics.registerFont(TTFont(regular_name, str(regular_path)))
            pdfmetrics.registerFont(TTFont(bold_name, str(bold_path)))
            return regular_name, bold_name

    return "Times-Roman", "Times-Bold"


@dataclass
class DocumentLineItem:
    line_no: int
    product_code: str
    description: str
    quantity: str
    unit: str
    unit_price: str
    discount: str
    vat: str
    total: str
    amount: str = ""


@dataclass
class DocumentTemplate:
    document_title: str
    filename_base: str
    document_kind: str = "STANDARD"
    document_id: str = ""
    company_name: str = "MeWa Automotive"
    company_address: str = "Istanbul, Turkiye"
    company_phone: str = "+90 212 000 00 00"
    company_email: str = "info@mewaautomotive.com"
    company_website: str = "www.mewaautomotive.com"
    company_tax_office: str = "Istanbul Tax Office"
    company_tax_number: str = "0000000000"
    invoice_number: str = ""
    invoice_date: str = ""
    due_date: str = ""
    expiry_date: str = ""
    currency: str = "USD"
    exchange_rate: str = "1"
    customer_name: str = ""
    customer_company_name: str = ""
    customer_address: str = ""
    customer_country: str = ""
    customer_tax_number: str = ""
    customer_phone: str = ""
    customer_email: str = ""
    customer_code: str = ""
    customer_whatsapp: str = ""
    bill_to_company: str = ""
    bill_to_address: str = ""
    bill_to_country: str = ""
    bill_to_contact: str = ""
    bill_to_phone: str = ""
    bill_to_email: str = ""
    bill_to_tax_number: str = ""
    ship_to_company: str = ""
    ship_to_address: str = ""
    ship_to_country: str = ""
    ship_to_contact: str = ""
    ship_to_phone: str = ""
    ship_to_email: str = ""
    ship_to_tax_number: str = ""
    payment_terms: str = ""
    delivery_terms: str = ""
    estimated_delivery: str = ""
    packing_type: str = ""
    subtotal: str = "0.00"
    discount_percent: str = "0.00"
    discount_total: str = "0.00"
    net_total: str = "0.00"
    vat_total: str = "0.00"
    grand_total: str = "0.00"
    notes: str = ""
    terms_conditions: str = ""
    bank_information: str = "Bank: Sample Bank | IBAN: TR00 0000 0000 0000 0000 0000 00"
    stamp_area_text: str = "Company Stamp"
    signature_text: str = "Authorized Signature"
    thank_you_message: str = "Thank you for your business."
    items: list[DocumentLineItem] = field(default_factory=list)

    def to_excel_headers(self) -> list[str]:
        return [
            "#",
            "Product Code",
            "Description",
            "Quantity",
            "Unit",
            "Unit Price",
            "Discount",
            "VAT",
            "Total",
        ]

    def to_excel_rows(self) -> list[list[str]]:
        return [
            [
                str(item.line_no),
                item.product_code,
                item.description,
                item.quantity,
                item.unit,
                item.unit_price,
                item.discount,
                item.vat,
                item.total,
            ]
            for item in self.items
        ]


class DocumentRenderer:
    def __init__(self, template: DocumentTemplate):
        self.template = template
        self.rotation = 0

    def page_count(self) -> int:
        item_count = max(1, len(self.template.items))
        first_page_capacity = 18
        other_page_capacity = 24
        if item_count <= first_page_capacity:
            return 1
        remaining = item_count - first_page_capacity
        pages_after_first = (remaining + other_page_capacity - 1) // other_page_capacity
        return 1 + pages_after_first

    def render_page(self, painter: QPainter, page_rect: QRect, page_number: int, total_pages: int):
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)
        logical_page = QRect(0, 0, 595, 842)
        painter.translate(page_rect.left(), page_rect.top())
        scale_x = page_rect.width() / float(logical_page.width())
        scale_y = page_rect.height() / float(logical_page.height())
        painter.scale(scale_x, scale_y)

        if self.rotation:
            cx = logical_page.center().x()
            cy = logical_page.center().y()
            painter.translate(cx, cy)
            painter.rotate(self.rotation)
            painter.translate(-cx, -cy)

        margin = 36
        content = QRect(
            logical_page.left() + margin,
            logical_page.top() + margin,
            logical_page.width() - (margin * 2),
            logical_page.height() - (margin * 2),
        )

        y = content.top()
        if page_number == 0:
            y = self._draw_header(painter, content, y)
            y = self._draw_title(painter, content, y)
            y = self._draw_info_blocks(painter, content, y)

        y = self._draw_items_table(painter, content, y, page_number)

        if page_number == total_pages - 1:
            y = self._draw_totals(painter, content, y)
            y = self._draw_notes_section(painter, content, y)
            self._draw_footer(painter, content, y)

        self._draw_page_number(painter, logical_page, page_number, total_pages)
        painter.restore()

    def _draw_header(self, painter: QPainter, rect: QRect, y: int) -> int:
        logo_size = 62
        logo_rect = QRect(rect.left(), y, logo_size, logo_size)
        logo = QPixmap(str(get_company_logo_path()))
        if not logo.isNull():
            painter.drawPixmap(logo_rect, logo.scaled(logo_size, logo_size, Qt.KeepAspectRatio, Qt.SmoothTransformation))

        company_x = logo_rect.right() + 14
        company_width = rect.width() - logo_size - 14
        company_rect = QRect(company_x, y, company_width, 86)

        painter.setPen(QPen(Qt.black))
        painter.setFont(QFont("Arial", 12, QFont.Bold))
        painter.drawText(company_rect, Qt.AlignTop | Qt.AlignLeft, self.template.company_name)

        painter.setFont(QFont("Arial", 8))
        company_lines = [
            self.template.company_address,
            f"Phone: {self.template.company_phone}",
            f"Email: {self.template.company_email}",
            f"Website: {self.template.company_website}",
            f"Tax Office: {self.template.company_tax_office}",
            f"Tax Number: {self.template.company_tax_number}",
        ]
        line_y = y + 16
        for line in company_lines:
            painter.drawText(QRect(company_x, line_y, company_width, 12), Qt.AlignLeft | Qt.AlignVCenter, line)
            line_y += 11

        divider_y = y + 84
        painter.setPen(QPen(Qt.black, 1))
        painter.drawLine(rect.left(), divider_y, rect.right(), divider_y)
        return divider_y + 10

    def _draw_title(self, painter: QPainter, rect: QRect, y: int) -> int:
        painter.setFont(QFont("Arial", 16, QFont.Bold))
        painter.drawText(QRect(rect.left(), y, rect.width(), 28), Qt.AlignCenter, self.template.document_title)
        painter.setPen(QPen(Qt.black, 1))
        painter.drawLine(rect.left(), y + 30, rect.right(), y + 30)
        return y + 38

    def _draw_info_blocks(self, painter: QPainter, rect: QRect, y: int) -> int:
        gap = 14
        block_width = (rect.width() - gap) // 2
        left_block = QRect(rect.left(), y, block_width, 128)
        right_block = QRect(rect.left() + block_width + gap, y, block_width, 128)

        self._draw_box(painter, left_block, "Invoice Information", [
            ("Invoice Number", self.template.invoice_number),
            ("Invoice Date", self.template.invoice_date),
            ("Due Date", self.template.due_date),
            ("Currency", self.template.currency),
            ("Exchange Rate", self.template.exchange_rate),
        ])

        self._draw_box(painter, right_block, "Customer Information", [
            ("Customer Name", self.template.customer_name),
            ("Company Name", self.template.customer_company_name),
            ("Address", self.template.customer_address),
            ("Country", self.template.customer_country),
            ("Tax Number", self.template.customer_tax_number),
            ("Phone", self.template.customer_phone),
            ("Email", self.template.customer_email),
        ])

        return y + 138

    def _draw_box(self, painter: QPainter, rect: QRect, title: str, rows: list[tuple[str, str]]):
        painter.setPen(QPen(Qt.black, 1))
        painter.drawRect(rect)

        painter.fillRect(QRect(rect.left(), rect.top(), rect.width(), 22), Qt.lightGray)
        painter.setFont(QFont("Arial", 10, QFont.Bold))
        painter.drawText(QRect(rect.left() + 8, rect.top(), rect.width() - 16, 22), Qt.AlignLeft | Qt.AlignVCenter, title)

        painter.setFont(QFont("Arial", 7))
        line_y = rect.top() + 28
        for label, value in rows:
            if line_y > rect.bottom() - 12:
                break
            painter.drawText(QRect(rect.left() + 8, line_y, rect.width() - 16, 11), Qt.AlignLeft | Qt.AlignVCenter, f"{label}: {value}")
            line_y += 12

    def _draw_items_table(self, painter: QPainter, rect: QRect, y: int, page_number: int) -> int:
        headers = ["#", "Product Code", "Description", "Quantity", "Unit", "Unit Price", "Discount", "VAT", "Total"]
        widths = [28, 80, 180, 62, 46, 78, 58, 52, 78]
        total_width = sum(widths)
        if total_width < rect.width():
            widths[-1] += rect.width() - total_width

        row_height = 18
        header_rect = QRect(rect.left(), y, rect.width(), row_height)
        painter.fillRect(header_rect, Qt.lightGray)
        painter.setPen(QPen(Qt.black, 1))
        painter.drawRect(header_rect)

        painter.setFont(QFont("Arial", 7, QFont.Bold))
        x = rect.left()
        for i, header in enumerate(headers):
            w = widths[i]
            cell = QRect(x, y, w, row_height)
            painter.drawRect(cell)
            painter.drawText(cell.adjusted(4, 0, -4, 0), Qt.AlignCenter, header)
            x += w

        y += row_height
        painter.setFont(QFont("Arial", 7))

        first_page_capacity = 18
        other_page_capacity = 24
        if page_number == 0:
            start = 0
            end = min(len(self.template.items), first_page_capacity)
        else:
            start = first_page_capacity + ((page_number - 1) * other_page_capacity)
            end = min(len(self.template.items), start + other_page_capacity)

        rows = self.template.items[start:end]
        if not rows:
            rows = [DocumentLineItem(1, "", "", "", "", "", "", "", "")]

        for item in rows:
            x = rect.left()
            values = [
                str(item.line_no),
                item.product_code,
                item.description,
                item.quantity,
                item.unit,
                item.unit_price,
                item.discount,
                item.vat,
                item.total,
            ]
            for i, value in enumerate(values):
                w = widths[i]
                cell = QRect(x, y, w, row_height)
                painter.drawRect(cell)
                align = Qt.AlignLeft | Qt.AlignVCenter
                if i in (0, 3, 5, 6, 7, 8):
                    align = Qt.AlignRight | Qt.AlignVCenter
                painter.drawText(cell.adjusted(4, 0, -4, 0), align, value)
                x += w
            y += row_height

        return y + 12

    def _draw_totals(self, painter: QPainter, rect: QRect, y: int) -> int:
        box_width = 280
        x = rect.right() - box_width
        line_height = 22
        labels = [
            ("Subtotal", self.template.subtotal),
            ("Discount", self.template.discount_total),
            ("VAT", self.template.vat_total),
            ("Grand Total", self.template.grand_total),
        ]
        painter.setFont(QFont("Arial", 9, QFont.Bold))
        for label, value in labels:
            row = QRect(x, y, box_width, line_height)
            painter.drawRect(row)
            painter.drawText(QRect(x + 8, y, 150, line_height), Qt.AlignLeft | Qt.AlignVCenter, label)
            painter.drawText(QRect(x + 160, y, box_width - 168, line_height), Qt.AlignRight | Qt.AlignVCenter, value)
            y += line_height
        return y + 8

    def _draw_notes_section(self, painter: QPainter, rect: QRect, y: int) -> int:
        notes = str(self.template.notes or "").strip()
        if not notes:
            return y
        notes_height = 56
        box = QRect(rect.left(), y, rect.width(), notes_height)
        painter.setPen(QPen(Qt.black, 1))
        painter.drawRect(box)
        painter.setFont(QFont("Arial", 8, QFont.Bold))
        painter.drawText(QRect(box.left() + 8, box.top() + 4, box.width() - 16, 14), Qt.AlignLeft | Qt.AlignVCenter, "Notes")
        painter.setFont(QFont("Arial", 7))
        painter.drawText(QRect(box.left() + 8, box.top() + 18, box.width() - 16, box.height() - 22), Qt.AlignLeft | Qt.TextWordWrap, notes)
        return y + notes_height + 8

    def _draw_footer(self, painter: QPainter, rect: QRect, y: int):
        footer_top = max(y, rect.bottom() - 104)
        painter.setFont(QFont("Arial", 8))
        painter.drawText(QRect(rect.left(), footer_top, rect.width(), 14), Qt.AlignLeft | Qt.AlignVCenter, f"Bank Information: {self.template.bank_information}")

        stamp_rect = QRect(rect.left(), footer_top + 20, 190, 76)
        sign_rect = QRect(rect.right() - 190, footer_top + 20, 190, 76)

        painter.drawRect(stamp_rect)
        painter.drawRect(sign_rect)
        painter.drawText(stamp_rect, Qt.AlignCenter, self.template.stamp_area_text)
        painter.drawText(sign_rect, Qt.AlignCenter, self.template.signature_text)

        painter.setFont(QFont("Arial", 8, QFont.Bold))
        painter.drawText(QRect(rect.left(), rect.bottom() - 20, rect.width(), 16), Qt.AlignCenter, self.template.thank_you_message)

    def _draw_page_number(self, painter: QPainter, page_rect: QRect, page_number: int, total_pages: int):
        painter.setFont(QFont("Arial", 8))
        text = f"Page {page_number + 1} / {total_pages}"
        painter.drawText(QRect(page_rect.left(), page_rect.bottom() - 24, page_rect.width() - 16, 16), Qt.AlignRight | Qt.AlignVCenter, text)


class ProformaRenderer:
    ORANGE = QColor("#F58220")
    BLACK = QColor("#000000")
    WHITE = QColor("#FFFFFF")
    LIGHT_GRAY = QColor("#F2F2F2")

    def __init__(self, template: DocumentTemplate):
        self.template = template
        self.rotation = 0

    def _logical_page(self) -> QRect:
        return QRect(0, 0, 595, 842)

    def page_count(self) -> int:
        item_count = max(1, len(self.template.items))
        first_page_capacity = 16
        other_page_capacity = 29
        if item_count <= first_page_capacity:
            return 1
        remaining = item_count - first_page_capacity
        return 1 + ((remaining + other_page_capacity - 1) // other_page_capacity)

    def _page_slice(self, page_number: int) -> tuple[int, int]:
        first_page_capacity = 16
        other_page_capacity = 29
        if page_number == 0:
            return 0, min(len(self.template.items), first_page_capacity)
        start = first_page_capacity + ((page_number - 1) * other_page_capacity)
        return start, min(len(self.template.items), start + other_page_capacity)

    def render_page(self, painter: QPainter, page_rect: QRect, page_number: int, total_pages: int):
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)

        logical = self._logical_page()
        painter.translate(page_rect.left(), page_rect.top())
        painter.scale(page_rect.width() / float(logical.width()), page_rect.height() / float(logical.height()))

        if self.rotation:
            cx = logical.center().x()
            cy = logical.center().y()
            painter.translate(cx, cy)
            painter.rotate(self.rotation)
            painter.translate(-cx, -cy)

        margin = 28
        content = QRect(
            logical.left() + margin,
            logical.top() + margin,
            logical.width() - (margin * 2),
            logical.height() - (margin * 2),
        )

        y = content.top()
        if page_number == 0:
            y = self._draw_header(painter, content, y)
            y = self._draw_customer_info(painter, content, y)
            y = self._draw_commercial_info(painter, content, y)

        y = self._draw_products_table(painter, content, y, page_number)

        if page_number == total_pages - 1:
            y = self._draw_totals(painter, content, y)
            self._draw_footer(painter, content, y)

        self._draw_page_number(painter, logical, page_number, total_pages)
        painter.restore()

    def _draw_header(self, painter: QPainter, rect: QRect, y: int) -> int:
        left_width = int(rect.width() * 0.58)
        right_x = rect.left() + left_width + 10
        right_w = rect.right() - right_x

        logo_size = 62
        logo_rect = QRect(rect.left(), y, logo_size, logo_size)
        logo = QPixmap(str(get_company_logo_path()))
        if not logo.isNull():
            painter.drawPixmap(logo_rect, logo.scaled(logo_size, logo_size, Qt.KeepAspectRatio, Qt.SmoothTransformation))

        info_x = logo_rect.right() + 10
        painter.setPen(QPen(self.BLACK))
        painter.setFont(QFont("Arial", 12, QFont.Bold))
        painter.drawText(QRect(info_x, y, left_width - logo_size - 12, 16), Qt.AlignLeft | Qt.AlignVCenter, self.template.company_name)

        painter.setFont(QFont("Arial", 8))
        lines = [
            self.template.company_address,
            f"Phone: {self.template.company_phone}",
            f"Email: {self.template.company_email}",
            f"Website: {self.template.company_website}",
        ]
        line_y = y + 18
        for line in lines:
            painter.drawText(QRect(info_x, line_y, left_width - logo_size - 12, 12), Qt.AlignLeft | Qt.AlignVCenter, line)
            line_y += 11

        title_box = QRect(right_x, y, right_w, 86)
        painter.fillRect(title_box, self.ORANGE)
        painter.setPen(QPen(self.WHITE))
        painter.setFont(QFont("Arial", 13, QFont.Bold))
        painter.drawText(QRect(title_box.left() + 8, title_box.top() + 6, title_box.width() - 16, 20), Qt.AlignCenter, "PROFORMA INVOICE")

        painter.setFont(QFont("Arial", 8, QFont.Bold))
        row_y = title_box.top() + 30
        details = [
            ("Proforma No", self.template.invoice_number),
            ("Date", self.template.invoice_date),
            ("Expiry Date", self.template.expiry_date or self.template.due_date),
            ("Currency", self.template.currency),
            ("Exchange", self.template.exchange_rate),
        ]
        for label, value in details:
            painter.drawText(QRect(title_box.left() + 8, row_y, 92, 11), Qt.AlignLeft | Qt.AlignVCenter, label)
            painter.drawText(QRect(title_box.left() + 102, row_y, title_box.width() - 110, 11), Qt.AlignRight | Qt.AlignVCenter, str(value or "-"))
            row_y += 11

        painter.setPen(QPen(self.BLACK, 1))
        painter.drawLine(rect.left(), y + 94, rect.right(), y + 94)
        return y + 102

    def _draw_customer_info(self, painter: QPainter, rect: QRect, y: int) -> int:
        gap = 10
        box_w = (rect.width() - gap) // 2
        left = QRect(rect.left(), y, box_w, 118)
        right = QRect(rect.left() + box_w + gap, y, box_w, 118)

        self._draw_info_box(
            painter,
            left,
            "Bill To",
            [
                ("Company", self.template.bill_to_company or self.template.customer_company_name),
                ("Address", self.template.bill_to_address or self.template.customer_address),
                ("Country", self.template.bill_to_country or self.template.customer_country),
                ("Contact", self.template.bill_to_contact or self.template.customer_name),
                ("Phone", self.template.bill_to_phone or self.template.customer_phone),
                ("Email", self.template.bill_to_email or self.template.customer_email),
                ("Tax No", self.template.bill_to_tax_number or self.template.customer_tax_number),
            ],
        )

        self._draw_info_box(
            painter,
            right,
            "Ship To",
            [
                ("Company", self.template.ship_to_company or self.template.customer_company_name),
                ("Address", self.template.ship_to_address or self.template.customer_address),
                ("Country", self.template.ship_to_country or self.template.customer_country),
                ("Contact", self.template.ship_to_contact or self.template.customer_name),
                ("Phone", self.template.ship_to_phone or self.template.customer_phone),
                ("Email", self.template.ship_to_email or self.template.customer_email),
                ("Tax No", self.template.ship_to_tax_number or self.template.customer_tax_number),
            ],
        )
        return y + 126

    def _draw_commercial_info(self, painter: QPainter, rect: QRect, y: int) -> int:
        box = QRect(rect.left(), y, rect.width(), 46)
        painter.setPen(QPen(self.BLACK, 1))
        painter.drawRect(box)
        painter.fillRect(QRect(box.left(), box.top(), box.width(), 18), self.LIGHT_GRAY)
        painter.setFont(QFont("Arial", 8, QFont.Bold))
        painter.drawText(QRect(box.left() + 8, box.top(), box.width() - 16, 18), Qt.AlignLeft | Qt.AlignVCenter, "Commercial Information")

        painter.setFont(QFont("Arial", 7))
        fields = [
            ("Payment Terms", self.template.payment_terms),
            ("Delivery Terms", self.template.delivery_terms),
            ("Estimated Delivery", self.template.estimated_delivery),
            ("Packing Type", self.template.packing_type),
        ]
        col_w = box.width() // 4
        for idx, (label, value) in enumerate(fields):
            col_x = box.left() + (idx * col_w)
            painter.drawText(QRect(col_x + 6, box.top() + 21, col_w - 12, 10), Qt.AlignLeft | Qt.AlignVCenter, label)
            painter.setFont(QFont("Arial", 7, QFont.Bold))
            painter.drawText(QRect(col_x + 6, box.top() + 31, col_w - 12, 12), Qt.AlignLeft | Qt.AlignVCenter, str(value or "-"))
            painter.setFont(QFont("Arial", 7))
        return y + 54

    def _draw_info_box(self, painter: QPainter, rect: QRect, title: str, rows: list[tuple[str, str]]) -> None:
        painter.setPen(QPen(self.BLACK, 1))
        painter.drawRect(rect)
        painter.fillRect(QRect(rect.left(), rect.top(), rect.width(), 18), self.LIGHT_GRAY)
        painter.setFont(QFont("Arial", 8, QFont.Bold))
        painter.drawText(QRect(rect.left() + 6, rect.top(), rect.width() - 12, 18), Qt.AlignLeft | Qt.AlignVCenter, title)

        painter.setFont(QFont("Arial", 7))
        line_y = rect.top() + 21
        for label, value in rows:
            if line_y > rect.bottom() - 10:
                break
            painter.drawText(QRect(rect.left() + 6, line_y, 70, 10), Qt.AlignLeft | Qt.AlignVCenter, f"{label}:")
            painter.drawText(QRect(rect.left() + 76, line_y, rect.width() - 82, 10), Qt.AlignLeft | Qt.AlignVCenter, str(value or "-"))
            line_y += 13

    def _draw_products_table(self, painter: QPainter, rect: QRect, y: int, page_number: int) -> int:
        headers = ["#", "Part Code", "Description", "Quantity", "Unit", "Unit Price", "Discount %", "Amount"]
        widths = [24, 76, 210, 54, 40, 64, 60, 67]
        table_width = sum(widths)
        if table_width < rect.width():
            widths[-1] += rect.width() - table_width

        row_h = 18
        x = rect.left()
        painter.setPen(QPen(self.BLACK, 1))
        painter.setFont(QFont("Arial", 7, QFont.Bold))
        for idx, header in enumerate(headers):
            cell = QRect(x, y, widths[idx], row_h)
            painter.fillRect(cell, self.ORANGE)
            painter.drawRect(cell)
            painter.setPen(QPen(self.WHITE))
            painter.drawText(cell.adjusted(3, 0, -3, 0), Qt.AlignCenter, header)
            painter.setPen(QPen(self.BLACK))
            x += widths[idx]

        y += row_h
        painter.setFont(QFont("Arial", 7))
        start, end = self._page_slice(page_number)
        rows = self.template.items[start:end]
        if not rows:
            rows = [DocumentLineItem(1, "", "", "", "", "", "", "", "", "")]

        for item in rows:
            x = rect.left()
            amount_text = item.amount or item.total
            values = [
                str(item.line_no),
                item.product_code,
                item.description,
                item.quantity,
                item.unit,
                item.unit_price,
                item.discount,
                amount_text,
            ]
            for col_idx, value in enumerate(values):
                cell = QRect(x, y, widths[col_idx], row_h)
                painter.drawRect(cell)
                align = Qt.AlignLeft | Qt.AlignVCenter
                if col_idx in (0, 3, 5, 6, 7):
                    align = Qt.AlignRight | Qt.AlignVCenter
                painter.drawText(cell.adjusted(3, 0, -3, 0), align, str(value or ""))
                x += widths[col_idx]
            y += row_h
        return y + 8

    def _draw_totals(self, painter: QPainter, rect: QRect, y: int) -> int:
        labels = [
            ("Subtotal", self.template.subtotal),
            ("Discount %", self.template.discount_percent),
            ("Discount Amount", self.template.discount_total),
            ("Net Total", self.template.net_total),
            ("VAT", self.template.vat_total),
            ("Grand Total", self.template.grand_total),
        ]
        w = 240
        x = rect.right() - w
        row_h = 18
        painter.setFont(QFont("Arial", 8, QFont.Bold))
        for label, value in labels:
            row = QRect(x, y, w, row_h)
            painter.drawRect(row)
            painter.drawText(QRect(x + 6, y, 128, row_h), Qt.AlignLeft | Qt.AlignVCenter, label)
            painter.drawText(QRect(x + 136, y, w - 142, row_h), Qt.AlignRight | Qt.AlignVCenter, str(value or "0.00"))
            y += row_h
        return y + 8

    def _draw_footer(self, painter: QPainter, rect: QRect, y: int) -> None:
        footer_top = max(y, rect.bottom() - 142)

        terms_rect = QRect(rect.left(), footer_top, int(rect.width() * 0.58), 58)
        bank_rect = QRect(terms_rect.right() + 8, footer_top, rect.right() - (terms_rect.right() + 8), 58)
        sign_rect = QRect(rect.right() - 170, footer_top + 66, 80, 56)
        stamp_rect = QRect(rect.right() - 82, footer_top + 66, 80, 56)

        for box in (terms_rect, bank_rect, sign_rect, stamp_rect):
            painter.drawRect(box)

        painter.setFont(QFont("Arial", 8, QFont.Bold))
        painter.drawText(QRect(terms_rect.left() + 6, terms_rect.top() + 3, terms_rect.width() - 12, 14), Qt.AlignLeft | Qt.AlignVCenter, "Terms & Conditions")
        painter.drawText(QRect(bank_rect.left() + 6, bank_rect.top() + 3, bank_rect.width() - 12, 14), Qt.AlignLeft | Qt.AlignVCenter, "Bank Information")

        painter.setFont(QFont("Arial", 7))
        painter.drawText(
            QRect(terms_rect.left() + 6, terms_rect.top() + 17, terms_rect.width() - 12, terms_rect.height() - 20),
            Qt.AlignLeft | Qt.TextWordWrap,
            str(self.template.terms_conditions or self.template.notes or "-"),
        )
        painter.drawText(
            QRect(bank_rect.left() + 6, bank_rect.top() + 17, bank_rect.width() - 12, bank_rect.height() - 20),
            Qt.AlignLeft | Qt.TextWordWrap,
            str(self.template.bank_information or "-"),
        )

        painter.setFont(QFont("Arial", 7, QFont.Bold))
        painter.drawText(sign_rect, Qt.AlignCenter, self.template.signature_text)
        painter.drawText(stamp_rect, Qt.AlignCenter, self.template.stamp_area_text)

        painter.setFont(QFont("Arial", 8, QFont.Bold))
        painter.drawText(QRect(rect.left(), rect.bottom() - 14, rect.width(), 12), Qt.AlignCenter, self.template.thank_you_message)

    def _draw_page_number(self, painter: QPainter, page_rect: QRect, page_number: int, total_pages: int) -> None:
        painter.setFont(QFont("Arial", 8))
        painter.drawText(QRect(page_rect.left(), page_rect.bottom() - 24, page_rect.width() - 10, 16), Qt.AlignRight | Qt.AlignVCenter, f"Page {page_number + 1} / {total_pages}")


class ProformaPlatypusRenderer:
    """Professional proforma renderer built only with ReportLab Platypus flowables."""

    @staticmethod
    def _styles():
        base = getSampleStyleSheet()
        return {
            "title": ParagraphStyle(
                "ProformaTitle",
                parent=base["Heading1"],
                fontName="Helvetica-Bold",
                fontSize=20,
                leading=22,
                textColor=colors.white,
                alignment=1,
            ),
            "section": ParagraphStyle(
                "SectionTitle",
                parent=base["Heading4"],
                fontName="Helvetica-Bold",
                fontSize=11,
                leading=13,
                textColor=colors.black,
            ),
            "normal": ParagraphStyle(
                "NormalText",
                parent=base["BodyText"],
                fontName="Helvetica",
                fontSize=9,
                leading=11,
                textColor=colors.black,
            ),
            "normal_oblique": ParagraphStyle(
                "NormalTextOblique",
                parent=base["BodyText"],
                fontName="Helvetica-Oblique",
                fontSize=9,
                leading=11,
                textColor=colors.black,
            ),
            "table_header": ParagraphStyle(
                "TableHeader",
                parent=base["BodyText"],
                fontName="Helvetica-Bold",
                fontSize=9,
                leading=11,
                textColor=colors.white,
                alignment=1,
            ),
            "table_body": ParagraphStyle(
                "TableBody",
                parent=base["BodyText"],
                fontName="Helvetica",
                fontSize=8.5,
                leading=10,
                textColor=colors.black,
            ),
            "table_body_right": ParagraphStyle(
                "TableBodyRight",
                parent=base["BodyText"],
                fontName="Helvetica",
                fontSize=8.5,
                leading=10,
                textColor=colors.black,
                alignment=2,
            ),
            "totals": ParagraphStyle(
                "Totals",
                parent=base["BodyText"],
                fontName="Helvetica-Bold",
                fontSize=10,
                leading=12,
                textColor=colors.black,
            ),
            "totals_right": ParagraphStyle(
                "TotalsRight",
                parent=base["BodyText"],
                fontName="Helvetica-Bold",
                fontSize=10,
                leading=12,
                textColor=colors.black,
                alignment=2,
            ),
        }

    @staticmethod
    def _safe_text(value: str) -> str:
        return str(value or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    @classmethod
    def _header(cls, template: DocumentTemplate, styles: dict):
        page_width = A4[0] - (15 * mm) - (15 * mm)
        logo_width = 72
        company_width = 250
        title_width = page_width - logo_width - company_width

        logo_flowable = Spacer(1, 1)
        logo_path = get_company_logo_path()
        if logo_path and Path(logo_path).exists():
            logo_flowable = RLImage(str(logo_path), width=60, height=60)

        company_lines = [
            f"<b>{cls._safe_text(template.company_name)}</b>",
            cls._safe_text(template.company_address),
            f"Phone: {cls._safe_text(template.company_phone)}",
            f"Email: {cls._safe_text(template.company_email)}",
            f"Website: {cls._safe_text(template.company_website)}",
            f"Tax Office: {cls._safe_text(template.company_tax_office)}",
            f"Tax Number: {cls._safe_text(template.company_tax_number)}",
        ]
        company_paragraph = Paragraph("<br/>".join(company_lines), styles["normal"])

        title_table = Table(
            [[Paragraph("PROFORMA INVOICE", styles["title"])]],
            colWidths=[title_width],
            rowHeights=[60],
        )
        title_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F58220")),
                    ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#F58220")),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ]
            )
        )

        top = Table(
            [[logo_flowable, company_paragraph, title_table]],
            colWidths=[logo_width, company_width, title_width],
        )
        top.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ]
            )
        )
        return top

    @classmethod
    def _party_box(cls, title: str, fields: list[tuple[str, str]], width: float, styles: dict):
        data = [[Paragraph(cls._safe_text(title), styles["section"])]]
        for label, value in fields:
            line = f"<b>{cls._safe_text(label)}:</b> {cls._safe_text(value) or '-'}"
            data.append([Paragraph(line, styles["normal"])])

        table = Table(data, colWidths=[width], rowHeights=[20] + [14] * 7)
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F2F2F2")),
                    ("BOX", (0, 0), (-1, -1), 0.8, colors.black),
                    ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#D9D9D9")),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 2),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ]
            )
        )
        return table

    @classmethod
    def _customer_boxes(cls, template: DocumentTemplate, styles: dict):
        page_width = A4[0] - (15 * mm) - (15 * mm)
        box_width = (page_width - 8) / 2.0

        bill_fields = [
            ("Company", template.bill_to_company or template.customer_company_name),
            ("Address", template.bill_to_address or template.customer_address),
            ("Country", template.bill_to_country or template.customer_country),
            ("Contact", template.bill_to_contact or template.customer_name),
            ("Phone", template.bill_to_phone or template.customer_phone),
            ("Email", template.bill_to_email or template.customer_email),
            ("Tax No", template.bill_to_tax_number or template.customer_tax_number),
        ]
        ship_fields = [
            ("Company", template.ship_to_company or template.customer_company_name),
            ("Address", template.ship_to_address or template.customer_address),
            ("Country", template.ship_to_country or template.customer_country),
            ("Contact", template.ship_to_contact or template.customer_name),
            ("Phone", template.ship_to_phone or template.customer_phone),
            ("Email", template.ship_to_email or template.customer_email),
            ("Tax No", template.ship_to_tax_number or template.customer_tax_number),
        ]

        wrapper = Table(
            [[cls._party_box("BILL TO", bill_fields, box_width, styles), cls._party_box("SHIP TO", ship_fields, box_width, styles)]],
            colWidths=[box_width, box_width],
        )
        wrapper.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
        return wrapper

    @classmethod
    def _commercial_info(cls, template: DocumentTemplate, styles: dict):
        data = [[
            Paragraph("<b>Payment Terms</b><br/>" + cls._safe_text(template.payment_terms or "-"), styles["normal"]),
            Paragraph("<b>Delivery Terms</b><br/>" + cls._safe_text(template.delivery_terms or "-"), styles["normal"]),
            Paragraph("<b>Estimated Delivery</b><br/>" + cls._safe_text(template.estimated_delivery or "-"), styles["normal"]),
            Paragraph("<b>Packing Type</b><br/>" + cls._safe_text(template.packing_type or "-"), styles["normal"]),
        ]]
        table = Table(data, colWidths=[127.5, 127.5, 127.5, 127.5])
        table.setStyle(
            TableStyle(
                [
                    ("BOX", (0, 0), (-1, -1), 0.8, colors.black),
                    ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D9D9D9")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        return table

    @classmethod
    def _product_table(cls, items: list[DocumentLineItem], styles: dict):
        col_widths = [24, 70, 178, 40, 40, 58, 50, 50]
        rows = [[
            Paragraph("#", styles["table_header"]),
            Paragraph("Part Code", styles["table_header"]),
            Paragraph("Description", styles["table_header"]),
            Paragraph("Qty", styles["table_header"]),
            Paragraph("Unit", styles["table_header"]),
            Paragraph("Unit Price", styles["table_header"]),
            Paragraph("Discount", styles["table_header"]),
            Paragraph("Amount", styles["table_header"]),
        ]]

        if not items:
            items = [DocumentLineItem(1, "", "", "", "", "", "", "", "", "")]

        for idx, item in enumerate(items, start=1):
            amount_text = item.amount or item.total
            rows.append(
                [
                    Paragraph(cls._safe_text(str(idx)), styles["table_body_right"]),
                    Paragraph(cls._safe_text(item.product_code), styles["table_body"]),
                    Paragraph(cls._safe_text(item.description), styles["table_body"]),
                    Paragraph(cls._safe_text(item.quantity), styles["table_body_right"]),
                    Paragraph(cls._safe_text(item.unit), styles["table_body"]),
                    Paragraph(cls._safe_text(item.unit_price), styles["table_body_right"]),
                    Paragraph(cls._safe_text(item.discount), styles["table_body_right"]),
                    Paragraph(cls._safe_text(amount_text), styles["table_body_right"]),
                ]
            )

        table = Table(rows, colWidths=col_widths, repeatRows=1)
        style_cmds = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.black),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("BOX", (0, 0), (-1, -1), 0.8, colors.black),
            ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CFCFCF")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("WORDWRAP", (2, 1), (2, -1), "CJK"),
        ]
        for body_row in range(1, len(rows)):
            bg = colors.white if body_row % 2 else colors.HexColor("#F5F5F5")
            style_cmds.append(("BACKGROUND", (0, body_row), (-1, body_row), bg))
        table.setStyle(TableStyle(style_cmds))
        return table

    @classmethod
    def _totals_table(cls, template: DocumentTemplate, styles: dict):
        totals_data = [
            [Paragraph("Subtotal", styles["totals"]), Paragraph(cls._safe_text(template.subtotal or "0.00"), styles["totals_right"])],
            [Paragraph("Discount", styles["totals"]), Paragraph(cls._safe_text(template.discount_total or "0.00"), styles["totals_right"])],
            [Paragraph("Net Total", styles["totals"]), Paragraph(cls._safe_text(template.net_total or template.subtotal or "0.00"), styles["totals_right"])],
            [Paragraph("Grand Total", styles["totals"]), Paragraph(cls._safe_text(template.grand_total or "0.00"), styles["totals_right"])],
        ]
        table = Table(totals_data, colWidths=[90, 120], hAlign="RIGHT")
        table.setStyle(
            TableStyle(
                [
                    ("BOX", (0, 0), (-1, -1), 0.8, colors.black),
                    ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D0D0D0")),
                    ("BACKGROUND", (0, 3), (-1, 3), colors.HexColor("#F58220")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        return table

    @classmethod
    def _footer(cls, template: DocumentTemplate, styles: dict):
        bank = Paragraph("<b>Bank Information</b><br/>" + cls._safe_text(template.bank_information or "-"), styles["normal"])

        signature_path = get_branding_asset_path("company_signature")
        stamp_path = get_branding_asset_path("company_stamp")

        signature_cell = Paragraph("Authorized Signature", styles["normal_oblique"])
        if signature_path.exists():
            signature_cell = RLImage(str(signature_path), width=100, height=36)

        stamp_cell = Paragraph("Company Stamp", styles["normal_oblique"])
        if stamp_path.exists():
            stamp_cell = RLImage(str(stamp_path), width=92, height=36)

        sign_stamp = Table([[signature_cell, stamp_cell]], colWidths=[110, 110], rowHeights=[54])
        sign_stamp.setStyle(
            TableStyle(
                [
                    ("BOX", (0, 0), (-1, -1), 0.8, colors.black),
                    ("INNERGRID", (0, 0), (-1, -1), 0.6, colors.black),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ]
            )
        )

        footer_table = Table([[bank, sign_stamp]], colWidths=[280, 230])
        footer_table.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("BOX", (0, 0), (0, 0), 0.8, colors.black),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        thanks = Paragraph("Thank you for your business.", ParagraphStyle("Thanks", parent=styles["normal_oblique"], alignment=1))
        return [footer_table, Spacer(1, 6), thanks]

    @classmethod
    def _draw_background_assets(cls, canvas, _doc):
        page_w, page_h = A4
        background = get_document_template_background_path("PROFORMA")
        if background.exists():
            canvas.saveState()
            canvas.drawImage(str(background), 0, 0, width=page_w, height=page_h, preserveAspectRatio=False, mask="auto")
            canvas.restoreState()

        watermark = get_branding_asset_path("watermark")
        if watermark.exists():
            canvas.saveState()
            try:
                canvas.setFillAlpha(0.08)
            except Exception:
                pass
            wm_w = 120 * mm
            wm_h = 120 * mm
            canvas.drawImage(
                str(watermark),
                (page_w - wm_w) / 2.0,
                (page_h - wm_h) / 2.0,
                width=wm_w,
                height=wm_h,
                preserveAspectRatio=True,
                mask="auto",
            )
            canvas.restoreState()

    @classmethod
    def export_to_path(cls, template: DocumentTemplate, save_path: str) -> tuple[bool, str | None]:
        try:
            styles = cls._styles()
            doc = SimpleDocTemplate(
                save_path,
                pagesize=A4,
                leftMargin=15 * mm,
                rightMargin=15 * mm,
                topMargin=20 * mm,
                bottomMargin=20 * mm,
                title="PROFORMA INVOICE",
                author=template.company_name or "MeWa Automotive",
            )

            story = [
                cls._header(template, styles),
                Spacer(1, 8),
                KeepTogether([
                    cls._customer_boxes(template, styles),
                    Spacer(1, 8),
                    cls._commercial_info(template, styles),
                ]),
                Spacer(1, 10),
            ]

            items = list(template.items or [])
            page_chunk = 24
            for idx in range(0, max(1, len(items)), page_chunk):
                story.append(cls._product_table(items[idx : idx + page_chunk], styles))
                if idx + page_chunk < len(items):
                    story.append(Spacer(1, 6))
                    story.append(PageBreak())

            story.extend([
                Spacer(1, 10),
                cls._totals_table(template, styles),
                Spacer(1, 12),
                KeepTogether(cls._footer(template, styles)),
            ])

            doc.build(story, onFirstPage=cls._draw_background_assets, onLaterPages=cls._draw_background_assets)
            return True, None
        except Exception as exc:
            return False, str(exc)


class PackingListPlatypusRenderer:
    BOTTOM_FOOTER_LINES = [
        "HEADOFFICE ADDRESS : Horozluhan Mah. Ahi Evran Cad. PC:42120 Selçuklu Konya / TURKEY",
        "FACTORY ADDRESS : Fevzi Çakmak Mah. Astim Industrial Zone PC:42200 Karatay Konya / TURKEY",
        "Tel: +90 532 499 68 89    WhatsApp: +90 532 499 68 89    e-Mail: export@mewaautomotive.com",
    ]

    @staticmethod
    def _styles():
        regular_font, bold_font = _resolve_unicode_fonts()
        base = getSampleStyleSheet()
        return {
            "title": ParagraphStyle(
                "PackingListTitle",
                parent=base["Heading1"],
                fontName=bold_font,
                fontSize=20,
                leading=22,
                textColor=colors.HexColor("#0F172A"),
                alignment=1,
            ),
            "section": ParagraphStyle(
                "PackingListSection",
                parent=base["Heading4"],
                fontName=bold_font,
                fontSize=10,
                leading=12,
                textColor=colors.HexColor("#0F172A"),
            ),
            "normal": ParagraphStyle(
                "PackingListNormal",
                parent=base["BodyText"],
                fontName=regular_font,
                fontSize=8.5,
                leading=10.5,
                textColor=colors.black,
            ),
            "small": ParagraphStyle(
                "PackingListSmall",
                parent=base["BodyText"],
                fontName=regular_font,
                fontSize=6.7,
                leading=8.2,
                textColor=colors.HexColor("#6B7280"),
                alignment=1,
            ),
            "table_header": ParagraphStyle(
                "PackingListHeader",
                parent=base["BodyText"],
                fontName=bold_font,
                fontSize=8,
                leading=10,
                textColor=colors.white,
                alignment=1,
            ),
            "table_body": ParagraphStyle(
                "PackingListBody",
                parent=base["BodyText"],
                fontName=regular_font,
                fontSize=8,
                leading=10,
                textColor=colors.black,
            ),
            "table_body_right": ParagraphStyle(
                "PackingListBodyRight",
                parent=base["BodyText"],
                fontName=regular_font,
                fontSize=8,
                leading=10,
                textColor=colors.black,
                alignment=2,
            ),
            "totals": ParagraphStyle(
                "PackingListTotals",
                parent=base["BodyText"],
                fontName=bold_font,
                fontSize=9,
                leading=11,
                textColor=colors.black,
            ),
            "totals_right": ParagraphStyle(
                "PackingListTotalsRight",
                parent=base["BodyText"],
                fontName=bold_font,
                fontSize=9,
                leading=11,
                textColor=colors.black,
                alignment=2,
            ),
        }

    @staticmethod
    def _safe_text(value: str) -> str:
        return str(value or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    @staticmethod
    def _format_eu_date(date_text: str) -> str:
        text = str(date_text or "").strip()
        match = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", text)
        if match:
            return f"{match.group(3)}/{match.group(2)}/{match.group(1)}"
        return text

    @classmethod
    def _header(cls, template: DocumentTemplate, styles: dict):
        page_width = A4[0] - (15 * mm) - (15 * mm)
        logo_width = 124
        company_width = 230
        title_width = page_width - logo_width - company_width

        logo_flowable = Spacer(1, 1)
        logo_path = _preferred_branding_asset("logo.png", "company_logo.png")
        if not logo_path.exists():
            logo_path = get_company_logo_path()
        if logo_path and Path(logo_path).exists():
            try:
                img = ImageReader(str(logo_path))
                iw, ih = img.getSize()
                target_width = 116.0
                target_height = max(28.0, (target_width * float(ih)) / float(iw or 1))
                logo_flowable = RLImage(str(logo_path), width=target_width, height=target_height)
            except Exception:
                logo_flowable = RLImage(str(logo_path), width=116, height=34)

        company_lines = [
            "<b>MeWa Automotive Ltd.Sti.</b>",
            "Konya / TURKIYE",
            "+90 532 499 68 89",
            "export@mewaautomotive.com",
            "www.mewaautomotive.com",
        ]
        company_paragraph = Paragraph(
            "<b>MeWa Automotive Ltd.Şti.</b><br/>"
            "<font size='8'>Konya / TURKIYE<br/>"
            "+90 532 499 68 89<br/>"
            "export@mewaautomotive.com<br/>"
            "www.mewaautomotive.com</font>",
            styles["normal"],
        )

        title_table = Table(
            [
                [Paragraph("PACKING LIST", styles["title"])],
            ],
            colWidths=[title_width],
            rowHeights=[62],
        )
        title_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FFFFFF")),
                    ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#D1D5DB")),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )

        top = Table(
            [[logo_flowable, company_paragraph, title_table]],
            colWidths=[logo_width, company_width, title_width],
        )
        top.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ]
            )
        )
        return top

    @classmethod
    def _section_box(cls, title: str, rows: list[tuple[str, str]], width: float, styles: dict):
        data = [[Paragraph(cls._safe_text(title), styles["section"])]]
        for label, value in rows:
            line = f"<b>{cls._safe_text(label)}:</b> {cls._safe_text(value) or '-'}"
            data.append([Paragraph(line, styles["normal"])])

        table = Table(data, colWidths=[width])
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F8FAFC")),
                    ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#CBD5E1")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#E2E8F0")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]
            )
        )
        return table

    @classmethod
    def _buyer_and_shipping(cls, template: DocumentTemplate, styles: dict):
        page_width = A4[0] - (15 * mm) - (15 * mm)
        box_width = (page_width - 8) / 2.0
        buyer_rows = [
            ("Customer", template.customer_company_name or template.customer_name),
            ("Customer Code", template.customer_code),
            ("Country", template.customer_country),
            ("Full Address", template.customer_address),
        ]
        shipping_rows = [
            ("Packing List No", template.invoice_number),
            ("Date", cls._format_eu_date(template.invoice_date)),
            ("Delivery Terms", template.delivery_terms),
        ]

        wrapper = Table(
            [[cls._section_box("Buyer Information", buyer_rows, box_width, styles), cls._section_box("Shipping Information", shipping_rows, box_width, styles)]],
            colWidths=[box_width, box_width],
        )
        wrapper.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
        return wrapper

    @classmethod
    def _pallet_sort_key(cls, pallet_name: str) -> tuple[int, str]:
        text = str(pallet_name or "").strip()
        match = re.search(r"(\d+)", text)
        if match:
            return int(match.group(1)), text.lower()
        return 10**9, text.lower()

    @classmethod
    def _item_table(cls, items: list[DocumentLineItem], styles: dict):
        col_widths = [62, 212, 64, 70, 74, 74]
        rows = [[
            Paragraph("PALLET", styles["table_header"]),
            Paragraph("DESCRIPTION", styles["table_header"]),
            Paragraph("QUANTITY", styles["table_header"]),
            Paragraph("QUANTITY WEIGHT", styles["table_header"]),
            Paragraph("TOTAL NET WEIGHT", styles["table_header"]),
            Paragraph("TOTAL GROSS WEIGHT", styles["table_header"]),
        ]]

        if not items:
            items = [DocumentLineItem(1, "", "", "", "", "", "", "", "", "")]

        grouped: dict[str, list[tuple[int, DocumentLineItem]]] = {}
        for index, item in enumerate(items):
            pallet = str(item.product_code or "").strip()
            grouped.setdefault(pallet, []).append((index, item))

        sorted_pallets = sorted(grouped.keys(), key=cls._pallet_sort_key)
        span_ranges: list[tuple[int, int]] = []
        row_cursor = 1

        for pallet in sorted_pallets:
            source_rows = sorted(grouped[pallet], key=lambda pair: pair[0])
            pallet_gross = 0.0
            for _, row_item in source_rows:
                pallet_gross += cls._parse_float(row_item.total or "0")

            pallet_gross_text = f"{pallet_gross:.3f} KG"
            start_row = row_cursor
            for order, (_, item) in enumerate(source_rows):
                pallet_cell_text = cls._safe_text(item.product_code) if order == 0 else ""
                gross_cell_text = cls._safe_text(pallet_gross_text) if order == 0 else ""
                rows.append(
                    [
                        Paragraph(pallet_cell_text, styles["table_body"]),
                        Paragraph(cls._safe_text(item.description), styles["table_body"]),
                        Paragraph(cls._safe_text(item.quantity), styles["table_body"]),
                        Paragraph(cls._safe_text(cls._format_weight_2(item.unit_price or "0.000 KG")), styles["table_body_right"]),
                        Paragraph(cls._safe_text(item.amount or "0.00 KG"), styles["table_body_right"]),
                        Paragraph(gross_cell_text, styles["table_body_right"]),
                    ]
                )
                row_cursor += 1

            end_row = row_cursor - 1
            if end_row > start_row:
                span_ranges.append((start_row, end_row))

        table = Table(rows, colWidths=col_widths, repeatRows=1)
        style_cmds = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F172A")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#D1D5DB")),
            ("INNERGRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D1D5DB")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("WORDWRAP", (1, 1), (1, -1), "CJK"),
            ("ALIGN", (0, 1), (0, -1), "CENTER"),
            ("ALIGN", (2, 1), (5, -1), "RIGHT"),
            ("ALIGN", (2, 0), (2, -1), "CENTER"),
            ("VALIGN", (0, 1), (0, -1), "MIDDLE"),
            ("VALIGN", (5, 1), (5, -1), "MIDDLE"),
        ]

        for start_row, end_row in span_ranges:
            style_cmds.append(("SPAN", (0, start_row), (0, end_row)))
            style_cmds.append(("SPAN", (5, start_row), (5, end_row)))
            style_cmds.append(("ALIGN", (0, start_row), (0, end_row), "CENTER"))
            style_cmds.append(("ALIGN", (5, start_row), (5, end_row), "CENTER"))
            style_cmds.append(("VALIGN", (0, start_row), (0, end_row), "MIDDLE"))
            style_cmds.append(("VALIGN", (5, start_row), (5, end_row), "MIDDLE"))

        for row_index in range(1, len(rows)):
            style_cmds.append(("BACKGROUND", (0, row_index), (-1, row_index), colors.white))
        table.setStyle(TableStyle(style_cmds))
        return table

    @staticmethod
    def _parse_float(value: str) -> float:
        txt = str(value or "").replace("KG", "").replace("PCS", "").strip()
        try:
            return float(txt or 0)
        except ValueError:
            return 0.0

    @classmethod
    def _format_weight_2(cls, value: str) -> str:
        return f"{cls._parse_float(value):.2f} KG"

    @classmethod
    def _format_pieces(cls, value: float) -> str:
        if float(value).is_integer():
            return f"{int(value)} PCS"
        return f"{value:.3f} PCS"

    @classmethod
    def _totals_table(cls, template: DocumentTemplate, styles: dict):
        total_pieces = 0.0
        total_net = 0.0
        total_gross = 0.0

        for item in template.items:
            total_pieces += cls._parse_float(item.quantity)
            total_net += cls._parse_float(item.amount)
            total_gross += cls._parse_float(item.total)

        unique_pallets = sorted({str(item.product_code or "").strip() for item in template.items if str(item.product_code or "").strip()})
        totals = [
            [Paragraph("TOTAL PALLETS", styles["totals"]), Paragraph(cls._safe_text(str(len(unique_pallets))), styles["totals_right"])],
            [Paragraph("TOTAL PIECES", styles["totals"]), Paragraph(cls._safe_text(cls._format_pieces(total_pieces)), styles["totals_right"])],
            [Paragraph("TOTAL NET WEIGHT", styles["totals"]), Paragraph(cls._safe_text(f"{total_net:.3f} KG"), styles["totals_right"])],
            [Paragraph("TOTAL GROSS WEIGHT", styles["totals"]), Paragraph(cls._safe_text(f"{total_gross:.3f} KG"), styles["totals_right"])],
        ]
        table = Table(totals, colWidths=[110, 120], hAlign="RIGHT")
        table.setStyle(
            TableStyle(
                [
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#D1D5DB")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D1D5DB")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        return table

    @classmethod
    def _footer(cls, template: DocumentTemplate, styles: dict):
        signature = Spacer(1, 1)
        signature_path = _preferred_branding_asset("company_signature.png", "signature.png")
        if not signature_path.exists():
            signature_path = get_branding_asset_path("company_signature")
        if signature_path.exists():
            try:
                img = ImageReader(str(signature_path))
                iw, ih = img.getSize()
                target_width = 166.0
                target_height = max(84.0, (target_width * float(ih)) / float(iw or 1))
                signature = RLImage(str(signature_path), width=target_width, height=target_height)
            except Exception:
                signature = RLImage(str(signature_path), width=166, height=88)

        notes_box = Paragraph("<b>NOTES</b><br/>" + cls._safe_text(template.notes or "-"), styles["normal"])

        signature_table = Table([[signature]], colWidths=[196], rowHeights=[110])
        signature_table.setStyle(
            TableStyle(
                [
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#D1D5DB")),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ]
            )
        )

        footer_table = Table(
            [[
                notes_box,
                signature_table,
            ]],
            colWidths=[334, 196],
        )
        footer_table.setStyle(
            TableStyle(
                [
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#D1D5DB")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D1D5DB")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("ALIGN", (1, 0), (1, 0), "CENTER"),
                    ("VALIGN", (1, 0), (1, 0), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ]
            )
        )
        return [footer_table]

    @classmethod
    def _draw_background_assets(cls, canvas, doc):
        canvas.saveState()
        left_x = float(doc.leftMargin)
        right_x = float(A4[0] - doc.rightMargin)
        footer_top = 22.0 * mm

        canvas.setStrokeColor(colors.HexColor("#D1D5DB"))
        canvas.setLineWidth(0.5)
        canvas.line(left_x, footer_top + 10, right_x, footer_top + 10)

        regular_font, _ = _resolve_unicode_fonts()
        canvas.setFont(regular_font, 6.7)
        canvas.setFillColor(colors.HexColor("#6B7280"))

        y = footer_top
        for line in cls.BOTTOM_FOOTER_LINES:
            canvas.drawCentredString((left_x + right_x) / 2.0, y, line)
            y -= 8

        canvas.restoreState()

    @classmethod
    def export_to_path(cls, template: DocumentTemplate, save_path: str) -> tuple[bool, str | None]:
        try:
            styles = cls._styles()
            doc = SimpleDocTemplate(
                save_path,
                pagesize=A4,
                leftMargin=15 * mm,
                rightMargin=15 * mm,
                topMargin=18 * mm,
                bottomMargin=34 * mm,
                title="PACKING LIST",
                author=template.company_name or "MeWa Automotive",
            )

            story = [
                cls._header(template, styles),
                Spacer(1, 8),
                cls._buyer_and_shipping(template, styles),
                Spacer(1, 10),
                cls._item_table(list(template.items or []), styles),
            ]

            story.extend([
                Spacer(1, 10),
                cls._totals_table(template, styles),
                Spacer(1, 12),
                KeepTogether(cls._footer(template, styles)),
            ])

            doc.build(story, onFirstPage=cls._draw_background_assets, onLaterPages=cls._draw_background_assets)
            return True, None
        except Exception as exc:
            return False, str(exc)


def create_renderer(template: DocumentTemplate):
    if str(template.document_kind or "").upper() == "PROFORMA":
        return ProformaRenderer(template)
    return DocumentRenderer(template)


class PDFExporter:
    @staticmethod
    def export_to_path(template: DocumentTemplate, save_path: str, rotation: int = 0) -> tuple[bool, str | None]:
        if str(template.document_kind or "").upper() == "PROFORMA":
            return ProformaPlatypusRenderer.export_to_path(template, save_path)
        if str(template.document_kind or "").upper() == "PACKING_LIST":
            return PackingListPlatypusRenderer.export_to_path(template, save_path)
        try:
            writer = QPdfWriter(save_path)
            writer.setPageSize(QPageSize(QPageSize.A4))
            writer.setPageOrientation(QPageLayout.Portrait)
            writer.setResolution(300)

            painter = QPainter(writer)
            renderer = create_renderer(template)
            renderer.rotation = rotation
            page_rectf: QRectF = writer.pageLayout().paintRectPixels(writer.resolution())
            page_rect = page_rectf.toRect()
            total_pages = renderer.page_count()
            for page_index in range(total_pages):
                if page_index > 0:
                    writer.newPage()
                renderer.render_page(painter, page_rect, page_index, total_pages)
            painter.end()
            return True, None
        except Exception as exc:
            return False, str(exc)


class PrintManager:
    @staticmethod
    def _print_pdf_file(parent, pdf_path: str) -> bool:
        if QPdfDocument is None:
            QMessageBox.warning(parent, "Warning", "Qt PDF module is not available for print preview.")
            return False

        document = QPdfDocument(parent)
        load_error = document.load(pdf_path)
        if load_error != QPdfDocument.Error.None_:
            QMessageBox.critical(parent, "Error", "Could not load generated proforma PDF for printing.")
            return False

        printer = QPrinter(QPrinter.HighResolution)
        printer.setPageSize(QPageSize(QPageSize.A4))
        printer.setPageOrientation(QPageLayout.Portrait)
        dialog = QPrintDialog(printer, parent)
        if dialog.exec() != QPrintDialog.Accepted:
            return False

        painter = QPainter(printer)
        for page_index in range(document.pageCount()):
            if page_index > 0:
                printer.newPage()
            page_rectf = printer.pageRect(QPrinter.DevicePixel)
            page_rect = page_rectf.toRect() if hasattr(page_rectf, "toRect") else page_rectf
            image = document.render(page_index, QSize(page_rect.width(), page_rect.height()))
            painter.drawImage(page_rect, image)
        painter.end()
        return True

    @staticmethod
    def print_template(parent, template: DocumentTemplate, rotation: int = 0) -> bool:
        if str(template.document_kind or "").upper() == "PROFORMA":
            handle = tempfile.NamedTemporaryFile(prefix="mewa_proforma_", suffix=".pdf", delete=False)
            handle.close()
            ok, error_message = ProformaPlatypusRenderer.export_to_path(template, handle.name)
            if not ok:
                QMessageBox.critical(parent, "Error", f"Could not create Proforma PDF for printing:\n{error_message}")
                return False
            return PrintManager._print_pdf_file(parent, handle.name)
        if str(template.document_kind or "").upper() == "PACKING_LIST":
            handle = tempfile.NamedTemporaryFile(prefix="mewa_packing_list_", suffix=".pdf", delete=False)
            handle.close()
            ok, error_message = PackingListPlatypusRenderer.export_to_path(template, handle.name)
            if not ok:
                QMessageBox.critical(parent, "Error", f"Could not create Packing List PDF for printing:\n{error_message}")
                return False
            return PrintManager._print_pdf_file(parent, handle.name)

        printer = QPrinter(QPrinter.HighResolution)
        printer.setPageSize(QPageSize(QPageSize.A4))
        printer.setPageOrientation(QPageLayout.Portrait)

        dialog = QPrintDialog(printer, parent)
        if dialog.exec() != QPrintDialog.Accepted:
            return False

        painter = QPainter(printer)
        renderer = create_renderer(template)
        renderer.rotation = rotation
        rectf = printer.pageRect(QPrinter.DevicePixel)
        page_rect = rectf.toRect() if hasattr(rectf, "toRect") else rectf
        total_pages = renderer.page_count()
        for page_index in range(total_pages):
            if page_index > 0:
                printer.newPage()
            renderer.render_page(painter, page_rect, page_index, total_pages)
        painter.end()
        return True


class ExcelExporter:
    @staticmethod
    def export_to_path(template: DocumentTemplate, save_path: str) -> bool:
        return ExcelService.export_excel_to_path(
            save_path,
            template.to_excel_headers(),
            template.to_excel_rows(),
            template.document_title,
        )


class DocumentToolbar(QToolBar):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMovable(False)
        self.setFloatable(False)


class DocumentPreviewWindow(QMainWindow):
    def __init__(self, template: DocumentTemplate, parent=None):
        super().__init__(parent)
        self.template = template
        self._pdf_backed_kinds = {"PROFORMA", "PACKING_LIST"}
        self._is_pdf_backed = str(template.document_kind or "").upper() in self._pdf_backed_kinds
        self._display_title = "PROFORMA INVOICE" if str(template.document_kind or "").upper() == "PROFORMA" else template.document_title
        self.renderer = create_renderer(template)
        self.rotation = 0
        self._current_pdf_path: Optional[str] = None
        self._pdf_document = None
        self._pdf_view = None

        self.setWindowTitle(f"Preview - {self._display_title}")
        self.resize(1100, 840)

        self.printer = QPrinter(QPrinter.HighResolution)
        self.printer.setPageSize(QPageSize(QPageSize.A4))
        self.printer.setPageOrientation(QPageLayout.Portrait)

        if self._is_pdf_backed and QPdfDocument is not None and QPdfView is not None:
            self._pdf_document = QPdfDocument(self)
            self._pdf_view = QPdfView(self)
            self._pdf_view.setDocument(self._pdf_document)
            self._pdf_view.setPageMode(QPdfView.PageMode.MultiPage)
            self._pdf_view.setZoomMode(QPdfView.ZoomMode.FitToWidth)
            self.setCentralWidget(self._pdf_view)
            self._refresh_pdf_preview()
        elif self._is_pdf_backed:
            info = QLabel("Qt PDF preview module is unavailable. PDF opened in default viewer.")
            info.setAlignment(Qt.AlignCenter)
            self.setCentralWidget(info)
            self._refresh_pdf_preview()
            if self._current_pdf_path and os.path.exists(self._current_pdf_path):
                QDesktopServices.openUrl(QUrl.fromLocalFile(self._current_pdf_path))
        else:
            self.preview = QPrintPreviewWidget(self.printer, self)
            self.preview.paintRequested.connect(self._paint_preview)
            self.setCentralWidget(self.preview)

        self.toolbar = DocumentToolbar(self)
        self.addToolBar(Qt.TopToolBarArea, self.toolbar)
        self._create_actions()

        if not self._is_pdf_backed:
            self.preview.updatePreview()

    def _create_actions(self):
        self.action_print = self.toolbar.addAction("Print")
        self.action_pdf = self.toolbar.addAction("Save PDF")
        self.action_excel = self.toolbar.addAction("Export Excel")

        self.share_button = QToolButton(self)
        self.share_button.setText("Share")
        self.share_button.setPopupMode(QToolButton.MenuButtonPopup)
        self.share_button.clicked.connect(self._on_share_default)
        self.share_menu = QMenu(self)
        self.share_button.setMenu(self.share_menu)
        self.share_widget_action = QWidgetAction(self)
        self.share_widget_action.setDefaultWidget(self.share_button)
        self.toolbar.addAction(self.share_widget_action)
        self._build_share_menu()

        self.toolbar.addSeparator()
        self.action_zoom_in = self.toolbar.addAction("Zoom In")
        self.action_zoom_out = self.toolbar.addAction("Zoom Out")
        self.action_fit = self.toolbar.addAction("Fit Page")
        self.action_rotate = self.toolbar.addAction("Rotate")
        self.toolbar.addSeparator()
        self.action_first = self.toolbar.addAction("First Page")
        self.action_prev = self.toolbar.addAction("Previous Page")
        self.action_next = self.toolbar.addAction("Next Page")
        self.action_last = self.toolbar.addAction("Last Page")

        self.action_print.triggered.connect(self._on_print)
        self.action_pdf.triggered.connect(self._on_save_pdf)
        self.action_excel.triggered.connect(self._on_export_excel)
        self.action_zoom_in.triggered.connect(self._on_zoom_in)
        self.action_zoom_out.triggered.connect(self._on_zoom_out)
        self.action_fit.triggered.connect(self._on_fit)
        self.action_rotate.triggered.connect(self._on_rotate)
        self.action_first.triggered.connect(self._on_first_page)
        self.action_prev.triggered.connect(self._on_prev_page)
        self.action_next.triggered.connect(self._on_next_page)
        self.action_last.triggered.connect(self._on_last_page)

        if self._is_pdf_backed:
            self.action_rotate.setEnabled(False)
            self.action_first.setEnabled(False)
            self.action_prev.setEnabled(False)
            self.action_next.setEnabled(False)
            self.action_last.setEnabled(False)

    def _build_share_menu(self):
        self.share_menu.clear()
        self.action_share_wa_desktop = self.share_menu.addAction("WhatsApp Desktop")
        self.action_share_wa_web = self.share_menu.addAction("WhatsApp Web")
        self.action_share_email = self.share_menu.addAction("Email")
        self.action_share_open_folder = self.share_menu.addAction("Open PDF Folder")
        self.action_share_copy_path = self.share_menu.addAction("Copy PDF Path")

        self.share_menu.addSeparator()
        for name in ["Microsoft Teams", "Telegram", "Google Drive", "OneDrive", "Dropbox", "FTP"]:
            action = self.share_menu.addAction(name)
            action.setEnabled(False)

        self.share_menu.addSeparator()
        self.action_share_remember = self.share_menu.addAction("Remember my default sharing method")
        self.action_share_remember.setCheckable(True)
        self.action_share_remember.setChecked(ShareService.is_remember_default_enabled())
        self.action_share_remember.toggled.connect(ShareService.set_remember_default_enabled)

        self.action_share_wa_desktop.triggered.connect(lambda: self._share_execute(ShareMethod.WHATSAPP_DESKTOP))
        self.action_share_wa_web.triggered.connect(lambda: self._share_execute(ShareMethod.WHATSAPP_WEB))
        self.action_share_email.triggered.connect(lambda: self._share_execute(ShareMethod.EMAIL))
        self.action_share_open_folder.triggered.connect(lambda: self._share_execute(ShareMethod.OPEN_FOLDER))
        self.action_share_copy_path.triggered.connect(lambda: self._share_execute(ShareMethod.COPY_PDF_PATH))

    def _on_share_default(self):
        self._share_execute(ShareService.get_default_method())

    def _build_share_context(self) -> ShareContext:
        if str(self.template.document_kind or "").upper() == "PACKING_LIST":
            message = (
                "Hello,\n\n"
                "Please find attached your Packing List.\n\n"
                "Packing List No:\n"
                f"{self.template.invoice_number}\n\n"
                "Best Regards\n\n"
                "MeWa Automotive Ltd.Şti."
            )
        else:
            message = (
                "Hello,\n\n"
                f"Please find attached your {self._display_title}.\n\n"
                f"Document No:\n{self.template.invoice_number}\n\n"
                "Best Regards\n\n"
                "MeWa Automotive Ltd.Şti."
            )

        return ShareContext(
            document_type=self._display_title,
            document_number=self.template.invoice_number,
            customer_code=self.template.customer_code,
            customer_name=self.template.customer_name,
            customer_email=self.template.customer_email,
            preferred_whatsapp=self.template.customer_whatsapp,
            message=message,
            ensure_pdf_path=self._ensure_pdf_for_share,
        )

    def _share_execute(self, method: str):
        context = self._build_share_context()
        ok = ShareService.execute(parent=self, method=method, context=context)
        if ok and ShareService.is_remember_default_enabled():
            ShareService.set_default_method(method)

    def _refresh_pdf_preview(self) -> None:
        if not self._is_pdf_backed:
            return
        if self._current_pdf_path is None:
            handle = tempfile.NamedTemporaryFile(prefix="mewa_preview_", suffix=".pdf", delete=False)
            handle.close()
            self._current_pdf_path = handle.name
        if str(self.template.document_kind or "").upper() == "PROFORMA":
            ok, error_message = ProformaPlatypusRenderer.export_to_path(self.template, self._current_pdf_path)
        else:
            ok, error_message = PackingListPlatypusRenderer.export_to_path(self.template, self._current_pdf_path)
        if not ok:
            QMessageBox.critical(self, "Error", f"Could not render preview PDF:\n{error_message}")
            return
        if self._pdf_document is None:
            return
        load_error = self._pdf_document.load(self._current_pdf_path)
        if load_error != QPdfDocument.Error.None_:
            QMessageBox.critical(self, "Error", "Could not load generated preview PDF.")

    def _on_zoom_in(self):
        if self._is_pdf_backed and self._pdf_view is not None:
            self._pdf_view.setZoomFactor(self._pdf_view.zoomFactor() * 1.1)
            return
        if self._is_pdf_backed:
            return
        self.preview.zoomIn()

    def _on_zoom_out(self):
        if self._is_pdf_backed and self._pdf_view is not None:
            self._pdf_view.setZoomFactor(max(0.25, self._pdf_view.zoomFactor() / 1.1))
            return
        if self._is_pdf_backed:
            return
        self.preview.zoomOut()

    def _on_fit(self):
        if self._is_pdf_backed and self._pdf_view is not None:
            self._pdf_view.setZoomMode(QPdfView.ZoomMode.FitToWidth)
            return
        if self._is_pdf_backed:
            return
        self.preview.fitInView()

    def _on_first_page(self):
        if self._is_pdf_backed:
            return
        self.preview.setCurrentPage(1)

    def _on_last_page(self):
        if self._is_pdf_backed:
            return
        self.preview.setCurrentPage(max(1, self.preview.pageCount()))

    def _paint_preview(self, printer: QPrinter):
        painter = QPainter(printer)
        self.renderer.rotation = self.rotation
        rectf = printer.pageRect(QPrinter.DevicePixel)
        page_rect = rectf.toRect() if hasattr(rectf, "toRect") else rectf
        total_pages = self.renderer.page_count()
        for page_index in range(total_pages):
            if page_index > 0:
                printer.newPage()
            self.renderer.render_page(painter, page_rect, page_index, total_pages)
        painter.end()

    def _on_print(self):
        PrintManager.print_template(self, self.template, self.rotation)

    def _on_save_pdf(self):
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save PDF",
            f"{self.template.filename_base}.pdf",
            "PDF Files (*.pdf)",
        )
        if not path:
            return
        ok, err = PDFExporter.export_to_path(self.template, path, self.rotation if not self._is_pdf_backed else 0)
        if not ok:
            QMessageBox.critical(self, "Error", f"Could not create PDF:\n{err}")
            return
        self._current_pdf_path = path
        if self._is_pdf_backed:
            self._refresh_pdf_preview()
        QMessageBox.information(self, "Success", "PDF generated successfully.")

    def _on_export_excel(self):
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Excel",
            f"{self.template.filename_base}.xlsx",
            "Excel Files (*.xlsx)",
        )
        if not path:
            return
        if not path.lower().endswith(".xlsx"):
            path = f"{path}.xlsx"
        if not ExcelExporter.export_to_path(self.template, path):
            QMessageBox.critical(self, "Error", "Could not create Excel.")
            return
        QMessageBox.information(self, "Success", "Excel exported successfully.")

    def _on_whatsapp(self):
        self._share_execute(ShareMethod.WHATSAPP_DESKTOP)

    def _on_email(self):
        self._share_execute(ShareMethod.EMAIL)

    def _on_prev_page(self):
        if self._is_pdf_backed:
            return
        current = self.preview.currentPage()
        self.preview.setCurrentPage(max(1, current - 1))

    def _on_next_page(self):
        if self._is_pdf_backed:
            return
        current = self.preview.currentPage()
        last = max(1, self.preview.pageCount())
        self.preview.setCurrentPage(min(last, current + 1))

    def _on_rotate(self):
        if self._is_pdf_backed:
            return
        self.rotation = (self.rotation + 90) % 360
        self.preview.updatePreview()

    def _ensure_pdf_for_share(self) -> Optional[str]:
        if self._current_pdf_path and os.path.exists(self._current_pdf_path):
            return self._current_pdf_path

        handle = tempfile.NamedTemporaryFile(prefix="mewa_preview_", suffix=".pdf", delete=False)
        handle.close()
        ok, _ = PDFExporter.export_to_path(self.template, handle.name, self.rotation if not self._is_pdf_backed else 0)
        if not ok:
            QMessageBox.critical(self, "Error", "Could not generate PDF for share.")
            return None
        self._current_pdf_path = handle.name
        return handle.name

    @staticmethod
    def _normalize_phone(phone: str) -> str:
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


class DocumentPreviewController:
    def __init__(
        self,
        *,
        parent,
        has_saved_document: Callable[[], bool],
        has_unsaved_changes: Callable[[], bool],
        save_callback: Callable[[bool], bool],
        template_provider: Callable[[], DocumentTemplate],
    ):
        self.parent = parent
        self.has_saved_document = has_saved_document
        self.has_unsaved_changes = has_unsaved_changes
        self.save_callback = save_callback
        self.template_provider = template_provider
        self._open_windows: list[DocumentPreviewWindow] = []

    def open_preview(self) -> bool:
        if not self.has_saved_document():
            QMessageBox.information(self.parent, "Preview", DEFAULT_MESSAGE_NEVER_SAVED)
            return False

        if self.has_unsaved_changes():
            decision = QMessageBox.question(
                self.parent,
                "Unsaved Changes",
                DEFAULT_MESSAGE_UNSAVED,
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
                QMessageBox.Yes,
            )
            if decision == QMessageBox.Cancel:
                return False
            if decision == QMessageBox.Yes and not self.save_callback(False):
                return False

        template = self.template_provider()
        preview_window = DocumentPreviewWindow(template=template, parent=self.parent)
        preview_window.show()
        preview_window.raise_()
        preview_window.activateWindow()
        self._open_windows.append(preview_window)
        return True


def build_template_signature(template: DocumentTemplate) -> str:
    payload = asdict(template)
    return str(payload)


def resolve_customer_details(*, customer_code: str, customer_name: str) -> dict[str, str]:
    db_path = Path(__file__).resolve().parent.parent / "database" / "mewa.db"
    if not db_path.exists():
        return {}

    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        if customer_code:
            cursor.execute(
                """
                SELECT
                    COALESCE(firma_unvani, '') AS name,
                    COALESCE(telefon, '') AS phone,
                    COALESCE(email, '') AS email,
                    COALESCE(adres, '') AS address,
                    COALESCE(ulke, '') AS country,
                    COALESCE(vergi_no, '') AS tax_number
                FROM cariler
                WHERE LOWER(COALESCE(cari_kodu, '')) = LOWER(?)
                LIMIT 1
                """,
                (customer_code,),
            )
            row = cursor.fetchone()
            if row is not None:
                return {
                    "name": str(row["name"] or ""),
                    "phone": str(row["phone"] or ""),
                    "email": str(row["email"] or ""),
                    "address": str(row["address"] or ""),
                    "country": str(row["country"] or ""),
                    "tax_number": str(row["tax_number"] or ""),
                }

        if customer_name:
            cursor.execute(
                """
                SELECT
                    COALESCE(firma_unvani, '') AS name,
                    COALESCE(telefon, '') AS phone,
                    COALESCE(email, '') AS email,
                    COALESCE(adres, '') AS address,
                    COALESCE(ulke, '') AS country,
                    COALESCE(vergi_no, '') AS tax_number
                FROM cariler
                WHERE LOWER(COALESCE(firma_unvani, '')) = LOWER(?)
                LIMIT 1
                """,
                (customer_name,),
            )
            row = cursor.fetchone()
            if row is not None:
                return {
                    "name": str(row["name"] or ""),
                    "phone": str(row["phone"] or ""),
                    "email": str(row["email"] or ""),
                    "address": str(row["address"] or ""),
                    "country": str(row["country"] or ""),
                    "tax_number": str(row["tax_number"] or ""),
                }

    return {}


def resolve_party_details(*, party_code: str, party_name: str) -> dict[str, str]:
    details = resolve_customer_details(customer_code=party_code, customer_name=party_name)
    if details:
        return details

    db_path = Path(__file__).resolve().parent.parent / "database" / "mewa.db"
    if not db_path.exists():
        return {}

    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        if party_code:
            cursor.execute(
                """
                SELECT
                    COALESCE(company_name, '') AS name,
                    COALESCE(phone, '') AS phone,
                    COALESCE(email, '') AS email,
                    COALESCE(address, '') AS address,
                    COALESCE(country, '') AS country,
                    COALESCE(tax_number, '') AS tax_number
                FROM suppliers
                WHERE LOWER(COALESCE(supplier_code, '')) = LOWER(?)
                LIMIT 1
                """,
                (party_code,),
            )
            row = cursor.fetchone()
            if row is not None:
                return {
                    "name": str(row["name"] or ""),
                    "phone": str(row["phone"] or ""),
                    "email": str(row["email"] or ""),
                    "address": str(row["address"] or ""),
                    "country": str(row["country"] or ""),
                    "tax_number": str(row["tax_number"] or ""),
                }

        if party_name:
            cursor.execute(
                """
                SELECT
                    COALESCE(company_name, '') AS name,
                    COALESCE(phone, '') AS phone,
                    COALESCE(email, '') AS email,
                    COALESCE(address, '') AS address,
                    COALESCE(country, '') AS country,
                    COALESCE(tax_number, '') AS tax_number
                FROM suppliers
                WHERE LOWER(COALESCE(company_name, '')) = LOWER(?)
                LIMIT 1
                """,
                (party_name,),
            )
            row = cursor.fetchone()
            if row is not None:
                return {
                    "name": str(row["name"] or ""),
                    "phone": str(row["phone"] or ""),
                    "email": str(row["email"] or ""),
                    "address": str(row["address"] or ""),
                    "country": str(row["country"] or ""),
                    "tax_number": str(row["tax_number"] or ""),
                }

    return {}


def _parse_structured_notes(notes_text: str) -> tuple[dict[str, str], str]:
    key_map = {
        "payment terms": "payment_terms",
        "delivery terms": "delivery_terms",
        "incoterms": "delivery_terms",
        "estimated delivery": "estimated_delivery",
        "packing type": "packing_type",
        "terms & conditions": "terms_conditions",
        "terms and conditions": "terms_conditions",
        "bank information": "bank_information",
        "ship to company": "ship_to_company",
        "ship to address": "ship_to_address",
        "ship to country": "ship_to_country",
        "ship to contact": "ship_to_contact",
        "ship to phone": "ship_to_phone",
        "ship to email": "ship_to_email",
        "ship to tax number": "ship_to_tax_number",
    }
    parsed: dict[str, str] = {}
    clean_lines: list[str] = []

    for raw in str(notes_text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        sep = ":" if ":" in line else ("=" if "=" in line else "")
        if not sep:
            clean_lines.append(raw)
            continue
        left, right = line.split(sep, 1)
        key = " ".join(left.strip().lower().replace("_", " ").split())
        target = key_map.get(key)
        if target is None:
            clean_lines.append(raw)
            continue
        parsed[target] = right.strip()

    return parsed, "\n".join(clean_lines).strip()


class ProformaTemplateBuilder:
    @staticmethod
    def _db_path() -> Path:
        return Path(__file__).resolve().parent.parent / "database" / "mewa.db"

    @classmethod
    def from_saved_proforma_id(cls, proforma_id: int) -> Optional[DocumentTemplate]:
        doc_id = int(proforma_id or 0)
        if doc_id <= 0:
            return None

        db_path = cls._db_path()
        if not db_path.exists():
            return None

        with sqlite3.connect(str(db_path)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT
                    ph.id,
                    ph.proforma_number AS invoice_number,
                    ph.issue_date AS invoice_date,
                    ph.expiry_date AS due_date,
                    COALESCE(ph.currency, 'USD') AS currency,
                    COALESCE(ph.exchange_rate, 1) AS exchange_rate,
                    COALESCE(ph.subtotal, 0) AS subtotal,
                    COALESCE(ph.discount_total, 0) AS discount_total,
                    COALESCE(ph.vat_total, 0) AS vat_total,
                    COALESCE(ph.grand_total, 0) AS grand_total,
                    COALESCE(ph.notes, '') AS notes,
                    COALESCE(ph.payment_terms, '') AS payment_terms,
                    COALESCE(ph.delivery_terms, '') AS delivery_terms,
                    COALESCE(c.cari_kodu, '') AS customer_code,
                    COALESCE(c.firma_unvani, '') AS customer_name,
                    COALESCE(c.adres, '') AS customer_address,
                    COALESCE(c.ulke, '') AS customer_country,
                    COALESCE(c.yetkili, '') AS customer_contact,
                    COALESCE(c.telefon, '') AS customer_phone,
                    COALESCE(c.email, '') AS customer_email,
                    COALESCE(c.vergi_no, '') AS customer_tax_number
                FROM proforma_headers ph
                LEFT JOIN cariler c ON c.id = ph.customer_id
                WHERE ph.id = ?
                LIMIT 1
                """,
                (doc_id,),
            )
            header = cursor.fetchone()
            use_legacy_sales_schema = False
            if header is None:
                cursor.execute(
                    """
                    SELECT
                        si.id,
                        si.invoice_number,
                        si.invoice_date,
                        si.due_date,
                        COALESCE(si.currency, 'USD') AS currency,
                        COALESCE(si.exchange_rate, 1) AS exchange_rate,
                        COALESCE(si.subtotal, 0) AS subtotal,
                        COALESCE(si.discount_total, 0) AS discount_total,
                        COALESCE(si.vat_total, 0) AS vat_total,
                        COALESCE(si.grand_total, 0) AS grand_total,
                        COALESCE(si.notes, '') AS notes,
                        COALESCE(si.payment_terms, '') AS payment_terms,
                        COALESCE(si.delivery_terms, '') AS delivery_terms,
                        COALESCE(c.cari_kodu, '') AS customer_code,
                        COALESCE(c.firma_unvani, '') AS customer_name,
                        COALESCE(c.adres, '') AS customer_address,
                        COALESCE(c.ulke, '') AS customer_country,
                        COALESCE(c.yetkili, '') AS customer_contact,
                        COALESCE(c.telefon, '') AS customer_phone,
                        COALESCE(c.email, '') AS customer_email,
                        COALESCE(c.vergi_no, '') AS customer_tax_number
                    FROM sales_invoices si
                    LEFT JOIN cariler c ON c.id = si.customer_id
                    WHERE si.id = ?
                    LIMIT 1
                    """,
                    (doc_id,),
                )
                header = cursor.fetchone()
                use_legacy_sales_schema = True
            if header is None:
                return None

            cursor.execute(
                """
                SELECT
                    pl.id,
                    COALESCE(st.stock_code, '') AS stock_code,
                    COALESCE(st.product_name, '') AS product_name,
                    COALESCE(st.hs_code, '') AS hs_code,
                    COALESCE(st.weight, 0) AS weight,
                    COALESCE(pl.quantity, 0) AS quantity,
                    COALESCE(pl.unit, '') AS unit,
                    COALESCE(pl.unit_price, 0) AS unit_price,
                    COALESCE(pl.discount_percent, 0) AS discount_percent,
                    COALESCE(pl.vat_percent, 0) AS vat_percent,
                    COALESCE(pl.line_total, 0) AS line_total
                FROM proforma_lines pl
                LEFT JOIN stoklar st ON st.id = pl.stock_id
                WHERE pl.proforma_id = ?
                ORDER BY pl.id
                """,
                (doc_id,),
            )
            item_rows = cursor.fetchall()
            if use_legacy_sales_schema:
                cursor.execute(
                    """
                    SELECT
                        sii.id,
                        COALESCE(st.stock_code, '') AS stock_code,
                        COALESCE(st.product_name, '') AS product_name,
                        COALESCE(st.hs_code, '') AS hs_code,
                        COALESCE(st.weight, 0) AS weight,
                        COALESCE(sii.quantity, 0) AS quantity,
                        COALESCE(sii.unit, '') AS unit,
                        COALESCE(sii.unit_price, 0) AS unit_price,
                        COALESCE(sii.discount_percent, 0) AS discount_percent,
                        COALESCE(sii.vat_percent, 0) AS vat_percent,
                        COALESCE(sii.line_total, 0) AS line_total
                    FROM sales_invoice_items sii
                    LEFT JOIN stoklar st ON st.id = sii.stock_id
                    WHERE sii.invoice_id = ?
                    ORDER BY sii.id
                    """,
                    (doc_id,),
                )
                item_rows = cursor.fetchall()

        notes_map, plain_notes = _parse_structured_notes(str(header["notes"] or ""))

        items: list[DocumentLineItem] = []
        for index, item in enumerate(item_rows, start=1):
            qty = float(item["quantity"] or 0)
            unit_price = float(item["unit_price"] or 0)
            discount_percent = float(item["discount_percent"] or 0)
            line_total = float(item["line_total"] or 0)
            amount = qty * unit_price * (1.0 - (discount_percent / 100.0))
            items.append(
                DocumentLineItem(
                    line_no=index,
                    product_code=str(item["stock_code"] or ""),
                    description=str(item["product_name"] or ""),
                    quantity=f"{qty:.3f}".rstrip("0").rstrip("."),
                    unit=str(item["unit"] or ""),
                    unit_price=f"{unit_price:.2f}",
                    discount=f"{discount_percent:.2f}",
                    vat=f"{float(item['vat_percent'] or 0):.2f}",
                    total=f"{line_total:.2f}",
                    amount=f"{amount:.2f}",
                )
            )

        subtotal = float(header["subtotal"] or 0)
        discount_total = float(header["discount_total"] or 0)
        vat_total = float(header["vat_total"] or 0)
        grand_total = float(header["grand_total"] or 0)
        net_total = subtotal - discount_total
        discount_percent = (discount_total / subtotal * 100.0) if subtotal > 0 else 0.0

        return DocumentTemplate(
            document_title="PROFORMA INVOICE",
            filename_base=str(header["invoice_number"] or "PROFORMA").replace("/", "-") or "PROFORMA",
            document_kind="PROFORMA",
            document_id=str(doc_id),
            invoice_number=str(header["invoice_number"] or ""),
            invoice_date=str(header["invoice_date"] or ""),
            due_date=str(header["due_date"] or ""),
            expiry_date=str(header["due_date"] or ""),
            currency=str(header["currency"] or "USD"),
            exchange_rate=f"{float(header['exchange_rate'] or 1):.6f}".rstrip("0").rstrip("."),
            customer_name=str(header["customer_name"] or ""),
            customer_company_name=str(header["customer_name"] or ""),
            customer_address=str(header["customer_address"] or ""),
            customer_country=str(header["customer_country"] or ""),
            customer_tax_number=str(header["customer_tax_number"] or ""),
            customer_phone=str(header["customer_phone"] or ""),
            customer_email=str(header["customer_email"] or ""),
            customer_code=str(header["customer_code"] or ""),
            customer_whatsapp=str(header["customer_phone"] or ""),
            bill_to_company=str(header["customer_name"] or ""),
            bill_to_address=str(header["customer_address"] or ""),
            bill_to_country=str(header["customer_country"] or ""),
            bill_to_contact=str(header["customer_contact"] or ""),
            bill_to_phone=str(header["customer_phone"] or ""),
            bill_to_email=str(header["customer_email"] or ""),
            bill_to_tax_number=str(header["customer_tax_number"] or ""),
            ship_to_company=notes_map.get("ship_to_company", ""),
            ship_to_address=notes_map.get("ship_to_address", ""),
            ship_to_country=notes_map.get("ship_to_country", ""),
            ship_to_contact=notes_map.get("ship_to_contact", ""),
            ship_to_phone=notes_map.get("ship_to_phone", ""),
            ship_to_email=notes_map.get("ship_to_email", ""),
            ship_to_tax_number=notes_map.get("ship_to_tax_number", ""),
            payment_terms=str(header["payment_terms"] or notes_map.get("payment_terms", "")),
            delivery_terms=str(header["delivery_terms"] or notes_map.get("delivery_terms", "")),
            estimated_delivery=notes_map.get("estimated_delivery", ""),
            packing_type=notes_map.get("packing_type", ""),
            subtotal=f"{subtotal:.2f}",
            discount_percent=f"{discount_percent:.2f}",
            discount_total=f"{discount_total:.2f}",
            net_total=f"{net_total:.2f}",
            vat_total=f"{vat_total:.2f}",
            grand_total=f"{grand_total:.2f}",
            notes=plain_notes,
            terms_conditions=notes_map.get("terms_conditions", ""),
            bank_information=notes_map.get("bank_information", "Bank: Sample Bank | IBAN: TR00 0000 0000 0000 0000 0000 00"),
            items=items,
        )

    @classmethod
    def from_saved_proforma_number(cls, proforma_number: str) -> Optional[DocumentTemplate]:
        value = str(proforma_number or "").strip()
        if not value:
            return None

        db_path = cls._db_path()
        if not db_path.exists():
            return None

        with sqlite3.connect(str(db_path)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id FROM proforma_headers WHERE proforma_number = ? LIMIT 1",
                (value,),
            )
            row = cursor.fetchone()
            if row is None:
                cursor.execute(
                    "SELECT id FROM sales_invoices WHERE invoice_number = ? LIMIT 1",
                    (value,),
                )
                row = cursor.fetchone()
            if row is None:
                return None
            return cls.from_saved_proforma_id(int(row["id"] or 0))
