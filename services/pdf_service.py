from datetime import datetime
from pathlib import Path
from typing import Sequence

from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QFileDialog, QMessageBox

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


class PDFService:
    @staticmethod
    def generate_pdf(
        parent,
        headers: Sequence[str],
        rows: Sequence[Sequence[object]],
        filename: str,
        title: str,
        logo_path: str | None = None,
    ) -> bool:
        try:
            PDFService._register_fonts()
        except Exception as exc:  # pragma: no cover - defensive fallback
            QMessageBox.critical(parent, "Hata", f"PDF motoru başlatılamadı:\n{exc}")
            return False

        save_path, _ = QFileDialog.getSaveFileName(
            parent,
            "PDF Dosyasını Kaydet",
            filename,
            "PDF Dosyaları (*.pdf)",
        )
        if not save_path:
            return False

        try:
            doc = SimpleDocTemplate(
                save_path,
                pagesize=landscape(A4),
                rightMargin=0.4 * inch,
                leftMargin=0.4 * inch,
                topMargin=0.5 * inch,
                bottomMargin=0.6 * inch,
            )
            story = []
            story.extend(PDFService._build_header(title, logo_path))

            if headers:
                table_data = [[str(header) for header in headers]]
                table_data.extend([[str(value) for value in row] for row in rows])
                col_widths = PDFService._compute_column_widths(headers, rows, doc.width)
                table = Table(
                    table_data,
                    repeatRows=1,
                    colWidths=col_widths,
                    hAlign="LEFT",
                )
                table.setStyle(
                    TableStyle(
                        [
                            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
                            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                            ("FONTNAME", (0, 0), (-1, 0), "DejaVuSans-Bold"),
                            ("FONTNAME", (0, 1), (-1, -1), "DejaVuSans"),
                            ("FONTSIZE", (0, 0), (-1, -1), 8),
                            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.white]),
                            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                            ("TOPPADDING", (0, 0), (-1, -1), 4),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                            ("LEFTPADDING", (0, 0), (-1, -1), 4),
                            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                        ]
                    )
                )
                story.append(table)
            else:
                story.append(Paragraph("Kayıt bulunamadı.", PDFService._body_style()))

            story.extend(PDFService._build_footer(len(rows)))
            doc.build(story, onFirstPage=PDFService._draw_canvas, onLaterPages=PDFService._draw_canvas)
            QMessageBox.information(parent, "Başarılı", "PDF dosyası başarıyla export edildi.")
            return True
        except Exception as exc:  # pragma: no cover - defensive fallback
            QMessageBox.critical(parent, "Hata", f"PDF oluşturulurken bir hata oluştu:\n{exc}")
            return False

    @staticmethod
    def _register_fonts() -> None:
        try:
            pdfmetrics.registerFont(TTFont("DejaVuSans", "c:/Windows/Fonts/arial.ttf"))
            pdfmetrics.registerFont(TTFont("DejaVuSans-Bold", "c:/Windows/Fonts/arialbd.ttf"))
        except Exception:
            pdfmetrics.registerFont(TTFont("DejaVuSans", "DejaVuSans.ttf"))
            pdfmetrics.registerFont(TTFont("DejaVuSans-Bold", "DejaVuSans-Bold.ttf"))

    @staticmethod
    def _build_header(title: str, logo_path: str | None):
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "CustomTitle",
            parent=styles["Title"],
            fontName="DejaVuSans-Bold",
            fontSize=20,
            leading=24,
            textColor=colors.HexColor("#0f172a"),
            spaceAfter=8,
        )
        meta_style = ParagraphStyle(
            "MetaStyle",
            parent=styles["BodyText"],
            fontName="DejaVuSans",
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#475569"),
            spaceAfter=4,
        )

        elements = []
        logo = PDFService._load_logo(logo_path)
        if logo is not None:
            elements.append(Image(logo, width=1.0 * inch, height=1.0 * inch, hAlign="LEFT"))
        elements.append(Paragraph(title, title_style))
        elements.append(Paragraph(datetime.now().strftime("Tarih: %d.%m.%Y"), meta_style))
        elements.append(Paragraph(datetime.now().strftime("Saat: %H:%M"), meta_style))
        elements.append(Spacer(1, 0.2 * inch))
        elements.append(Paragraph("─" * 60, ParagraphStyle("Divider", parent=styles["BodyText"], fontName="DejaVuSans", fontSize=10, textColor=colors.HexColor("#cbd5e1"))))
        elements.append(Spacer(1, 0.2 * inch))
        return elements

    @staticmethod
    def _build_footer(total_records: int):
        styles = getSampleStyleSheet()
        footer_style = ParagraphStyle(
            "FooterStyle",
            parent=styles["BodyText"],
            fontName="DejaVuSans",
            fontSize=8,
            leading=10,
            textColor=colors.HexColor("#64748b"),
        )
        return [Spacer(1, 0.3 * inch), Paragraph(f"Toplam Kayıt: {total_records}", footer_style), Paragraph("Generated by MeWa ERP Professional", footer_style)]

    @staticmethod
    def _draw_canvas(canvas, doc) -> None:
        canvas.saveState()
        canvas.setFont("DejaVuSans", 8)
        canvas.setFillColor(colors.HexColor("#64748b"))
        canvas.drawString(0.45 * inch, 0.3 * inch, f"Sayfa {canvas.getPageNumber()}")
        canvas.drawRightString(landscape(A4)[0] - 0.45 * inch, 0.3 * inch, "MeWa ERP Professional")
        canvas.restoreState()

    @staticmethod
    def _compute_column_widths(headers: Sequence[str], rows: Sequence[Sequence[object]], page_width: float):
        if not headers:
            return []

        max_lengths = []
        for index, header in enumerate(headers):
            longest = len(str(header))
            for row in rows:
                value = str(row[index]) if index < len(row) else ""
                longest = max(longest, len(value))
            max_lengths.append(longest)

        total_width = sum(max(80, value * 7) for value in max_lengths)
        available_width = page_width - 0.8 * inch
        if total_width <= available_width:
            return [max(80, value * 7) for value in max_lengths]

        scale = available_width / total_width
        return [max(70, int(value * scale)) for value in [max(80, value * 7) for value in max_lengths]]

    @staticmethod
    def _load_logo(logo_path: str | None):
        if logo_path:
            path = Path(logo_path)
            if path.exists():
                pixmap = QPixmap(str(path))
                if not pixmap.isNull():
                    return ImageReader(str(path))

        for candidate in [
            Path("assets/logo.png"),
            Path("assets/logo.jpg"),
            Path("assets/logo.jpeg"),
            Path("assets/MeWaLogo.png"),
            Path("logo.png"),
            Path("logo.jpg"),
        ]:
            if candidate.exists():
                pixmap = QPixmap(str(candidate))
                if not pixmap.isNull():
                    return ImageReader(str(candidate))
        return None
