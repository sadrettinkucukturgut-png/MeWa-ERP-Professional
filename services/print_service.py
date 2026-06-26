from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Sequence

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices, QPixmap
from PySide6.QtPrintSupport import QPrintDialog, QPrinter
from PySide6.QtWidgets import QMessageBox
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas


class PrintService:
    @staticmethod
    def print_report(parent, headers: Sequence[str], rows: Sequence[Sequence[object]], title: str, logo_path: str | None = None) -> bool:
        printer = QPrinter(QPrinter.HighResolution)
        dialog = QPrintDialog(printer, parent)
        if dialog.exec() != QPrintDialog.Accepted:
            return False

        try:
            buffer = BytesIO()
            report_canvas = canvas.Canvas(buffer, pagesize=landscape(A4))
            report_canvas.setFont("Helvetica-Bold", 16)
            report_canvas.setFillColor(colors.HexColor("#0f172a"))
            report_canvas.drawString(0.5 * inch, 10.2 * inch, title)
            report_canvas.setFont("Helvetica", 10)
            report_canvas.setFillColor(colors.HexColor("#475569"))
            report_canvas.drawString(0.5 * inch, 9.9 * inch, f"Tarih: {datetime.now().strftime('%d.%m.%Y %H:%M')}")
            report_canvas.setStrokeColor(colors.HexColor("#cbd5e1"))
            report_canvas.line(0.5 * inch, 9.7 * inch, 11.0 * inch, 9.7 * inch)
            report_canvas.setFont("Helvetica-Bold", 9)
            report_canvas.setFillColor(colors.black)
            y = 9.2 * inch
            x = 0.5 * inch
            cell_height = 0.24 * inch
            column_widths = []
            if headers:
                available_width = 10.5 * inch
                total_text_width = sum(max(70, len(str(header)) * 7) for header in headers)
                scale = available_width / total_text_width if total_text_width else 1.0
                for header in headers:
                    column_widths.append(max(70, int(len(str(header)) * 7 * scale)))

                for idx, header in enumerate(headers):
                    report_canvas.rect(x, y, column_widths[idx], cell_height)
                    report_canvas.drawString(x + 4, y + 4, str(header))
                    x += column_widths[idx]
                y -= cell_height
                report_canvas.setFont("Helvetica", 8)
                for row in rows:
                    if y < 0.8 * inch:
                        report_canvas.showPage()
                        y = 10.2 * inch
                    x = 0.5 * inch
                    for idx, value in enumerate(row):
                        width = column_widths[idx] if idx < len(column_widths) else 70
                        report_canvas.rect(x, y, width, cell_height)
                        report_canvas.drawString(x + 4, y + 4, str(value))
                        x += width
                    y -= cell_height

            report_canvas.setFont("Helvetica-Oblique", 8)
            report_canvas.setFillColor(colors.HexColor("#64748b"))
            report_canvas.drawString(0.5 * inch, 0.4 * inch, f"Toplam Kayıt: {len(rows)}")
            report_canvas.drawRightString(11.0 * inch, 0.4 * inch, "MeWa ERP Professional")
            report_canvas.showPage()
            report_canvas.save()

            pdf_bytes = buffer.getvalue()
            if pdf_bytes:
                import tempfile

                with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_file:
                    tmp_file.write(pdf_bytes)
                    temp_path = tmp_file.name
                QDesktopServices.openUrl(QUrl.fromLocalFile(temp_path))
            return True
        except Exception as exc:  # pragma: no cover - defensive fallback
            QMessageBox.critical(parent, "Hata", f"Yazdırma sırasında bir hata oluştu:\n{exc}")
            return False
