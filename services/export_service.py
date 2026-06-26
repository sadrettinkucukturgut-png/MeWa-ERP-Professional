from datetime import datetime
from pathlib import Path
from typing import Sequence

from PySide6.QtCore import QMarginsF, Qt
from PySide6.QtGui import QColor, QFont, QPageLayout, QPageSize, QPainter, QPixmap
from PySide6.QtPrintSupport import QPrinter
from PySide6.QtWidgets import QFileDialog, QMessageBox


class ExportService:
    @staticmethod
    def export_table_to_excel(
        parent,
        headers: Sequence[str],
        rows: Sequence[Sequence[object]],
        filename: str,
        sheet_title: str = "Liste",
        success_message: str = "Excel dosyası başarıyla export edildi.",
    ) -> bool:
        try:
            from openpyxl import Workbook  # type: ignore
        except ImportError:
            QMessageBox.critical(
                parent,
                "Hata",
                "Excel export için openpyxl paketi gereklidir.\nLütfen 'pip install openpyxl' ile kurun.",
            )
            return False

        save_path, _ = QFileDialog.getSaveFileName(
            parent,
            "Excel Dosyasını Kaydet",
            filename,
            "Excel Dosyaları (*.xlsx)",
        )
        if not save_path:
            return False

        workbook = Workbook()
        sheet = workbook.active
        sheet.title = sheet_title[:31]
        sheet.append(["" if value is None else str(value) for value in headers])

        for row in rows:
            sheet.append(["" if value is None else str(value) for value in row])

        workbook.save(save_path)
        QMessageBox.information(parent, "Başarılı", success_message)
        return True

    @staticmethod
    def export_table_to_pdf(
        parent,
        headers: Sequence[str],
        rows: Sequence[Sequence[object]],
        filename: str,
        title: str,
        logo_path: str | None = None,
    ) -> bool:
        save_path, _ = QFileDialog.getSaveFileName(
            parent,
            "PDF Dosyasını Kaydet",
            filename,
            "PDF Dosyaları (*.pdf)",
        )
        if not save_path:
            return False

        printer = QPrinter(QPrinter.HighResolution)
        printer.setOutputFormat(QPrinter.PdfFormat)
        printer.setOutputFileName(save_path)
        printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
        printer.setPageMargins(QMarginsF(16, 16, 16, 16), QPageLayout.Point)
        printer.setCreator("MeWa ERP")
        printer.setDocName(title)

        painter = QPainter(printer)
        try:
            page_rect = printer.pageLayout().paintRect(QPageLayout.Point)
            left = int(page_rect.left())
            top = int(page_rect.top())
            width = int(page_rect.width())
            height = int(page_rect.height())

            logo = ExportService._load_logo(logo_path)
            y = top + 12
            if logo is not None:
                painter.drawPixmap(left, y, 60, 60, logo)
                y += 74

            painter.setFont(QFont("Segoe UI", 16, QFont.Bold))
            painter.setPen(QColor("#0f172a"))
            painter.drawText(left, y, title)

            painter.setFont(QFont("Segoe UI", 9))
            painter.setPen(QColor("#475569"))
            painter.drawText(left, y + 20, datetime.now().strftime("Tarih: %d.%m.%Y %H:%M"))

            painter.setPen(QColor("#cbd5e1"))
            painter.drawLine(left, y + 38, left + width, y + 38)
            painter.setPen(Qt.black)

            if not headers:
                return True

            table_width = width - 8
            col_width = max(60, int(table_width / max(1, len(headers))))
            row_height = 18
            header_height = 20
            start_y = y + 46

            current_rows = list(rows)
            page_index = 0
            while current_rows:
                if page_index > 0:
                    printer.newPage()
                    y = top + 12
                    painter.setFont(QFont("Segoe UI", 16, QFont.Bold))
                    painter.setPen(QColor("#0f172a"))
                    painter.drawText(left, y, title)
                    painter.setFont(QFont("Segoe UI", 9))
                    painter.setPen(QColor("#475569"))
                    painter.drawText(left, y + 20, datetime.now().strftime("Tarih: %d.%m.%Y %H:%M"))
                    painter.setPen(QColor("#cbd5e1"))
                    painter.drawLine(left, y + 38, left + width, y + 38)
                    painter.setPen(Qt.black)
                    start_y = y + 46

                painter.setFont(QFont("Segoe UI", 9, QFont.Bold))
                painter.setPen(QColor("#ffffff"))
                painter.setBrush(QColor("#0f172a"))
                painter.drawRect(left, start_y, table_width, header_height)
                painter.setPen(QColor("#ffffff"))
                for col_idx, header in enumerate(headers):
                    x = left + col_idx * col_width
                    painter.drawText(x + 4, start_y + 2, col_width - 4, header_height - 4, Qt.AlignLeft | Qt.AlignVCenter, str(header))

                y_pos = start_y + header_height
                painter.setPen(QColor("#334155"))
                painter.setFont(QFont("Segoe UI", 8))
                row_count_for_page = 0
                while row_count_for_page < len(current_rows):
                    if y_pos + row_height > top + height - 16:
                        break
                    row = current_rows[row_count_for_page]
                    painter.setBrush(QColor("#f8fafc") if row_count_for_page % 2 == 0 else QColor("#ffffff"))
                    painter.drawRect(left, y_pos, table_width, row_height)
                    painter.setPen(QColor("#0f172a"))
                    for col_idx, value in enumerate(row):
                        x = left + col_idx * col_width
                        painter.drawText(x + 4, y_pos + 1, col_width - 4, row_height - 2, Qt.AlignLeft | Qt.AlignVCenter, str(value))
                    y_pos += row_height
                    row_count_for_page += 1

                current_rows = current_rows[row_count_for_page:]
                page_index += 1

            return True
        finally:
            if painter.isActive():
                painter.end()

    @staticmethod
    def _load_logo(logo_path: str | None):
        if logo_path:
            path = Path(logo_path)
            if path.exists():
                pixmap = QPixmap(str(path))
                if not pixmap.isNull():
                    return pixmap

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
                    return pixmap
        return None
