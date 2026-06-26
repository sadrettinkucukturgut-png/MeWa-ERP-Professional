from pathlib import Path
import sqlite3

from PySide6.QtCore import Qt, QSettings
from PySide6.QtGui import QAction, QPainter
from PySide6.QtPrintSupport import QPrinter
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QGridLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from models.cari_model import CariModel
from ui.new_cari_dialog import NewCariDialog


class CariListPage(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Cari Listesi")
        self.resize(900, 500)

        self.db_path = Path(__file__).resolve().parent.parent / "database" / "mewa.db"

        self._setup_ui()
        self.load_cari_list()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        self.page_title = QLabel("📋 Cari Listesi")
        self.page_title.setAlignment(Qt.AlignCenter)
        self.page_title.setStyleSheet(
            ""
            "font-size: 24px;"
            "font-weight: bold;"
            "padding: 10px 0;"
            ""
        )
        layout.addWidget(self.page_title)

        search_label = QLabel("Ara:")
        search_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(search_label)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Cari Kodu, Firma Ünvanı, Yetkili, Telefon, Şehir veya Ülke")
        self.search_input.textChanged.connect(self._handle_search)
        layout.addWidget(self.search_input)

        self.toolbar = QToolBar()
        self.toolbar.setMovable(False)
        layout.addWidget(self.toolbar)

        self.action_yeni_cari = QAction("➕ Yeni Cari", self)
        self.action_yeni_cari.triggered.connect(self._yeni_cari_ekle)
        self.toolbar.addAction(self.action_yeni_cari)

        self.toolbar.addSeparator()

        self.action_excel = QAction("📄 Excel'e Aktar", self)
        self.action_excel.triggered.connect(self._export_to_excel)
        self.toolbar.addAction(self.action_excel)

        self.action_pdf = QAction("🖨 PDF", self)
        self.action_pdf.triggered.connect(self._export_to_pdf)
        self.toolbar.addAction(self.action_pdf)

        self.action_print = QAction("🖨 Yazdır", self)
        self.action_print.triggered.connect(self._print_table)
        self.toolbar.addAction(self.action_print)

        self.toolbar.addSeparator()

        self.action_columns = QAction("⚙️ Kolonlar", self)
        self.action_columns.triggered.connect(self._show_column_menu)
        self.toolbar.addAction(self.action_columns)

        self.stats_layout = QGridLayout()
        self.stats_layout.setSpacing(12)
        self.stats_container = QFrame()
        self.stats_container.setStyleSheet(
            "QFrame{background-color:#f5f7fb; border:1px solid #dfe6ee; border-radius:12px;}"
        )
        self.stats_container.setLayout(self.stats_layout)
        layout.addWidget(self.stats_container)

        self.stats_cards = []
        for title, icon in [
            ("Toplam Cari", "📋"),
            ("Firma Sayısı", "🏢"),
            ("Şehir Sayısı", "🏙"),
            ("Ülke Sayısı", "🌍"),
        ]:
            card = QFrame()
            card.setStyleSheet(
                "QFrame{background-color:white; border:1px solid #e2e8f0; border-radius:12px;}"
            )
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(14, 14, 14, 14)
            card_layout.setSpacing(6)

            value_label = QLabel("0")
            value_label.setObjectName("statValue")
            value_label.setStyleSheet("font-size: 22px; font-weight: bold; color: #1f2937;")
            title_label = QLabel(f"{icon} {title}")
            title_label.setStyleSheet("font-size: 12px; color: #64748b;")

            card_layout.addWidget(value_label)
            card_layout.addWidget(title_label)

            self.stats_layout.addWidget(card, 0, len(self.stats_cards))
            self.stats_cards.append((title, value_label))

        self.cari_table = QTableWidget()
        self.cari_table.setObjectName("cariTable")
        self.column_labels = [
            "Cari Kodu",
            "Firma Ünvanı",
            "Yetkili",
            "Telefon",
            "Şehir",
            "Ülke",
        ]
        self.cari_table.setColumnCount(len(self.column_labels))
        self.cari_table.setHorizontalHeaderLabels(self.column_labels)
        self.cari_table.setAlternatingRowColors(True)
        self.cari_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.cari_table.setSelectionMode(QTableWidget.SingleSelection)
        self.cari_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.cari_table.setSortingEnabled(False)
        self.cari_table.verticalHeader().setVisible(False)
        self.cari_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.cari_table.doubleClicked.connect(self.cari_ac)
        self.cari_table.customContextMenuRequested.connect(self._show_context_menu)

        header = self.cari_table.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(QHeaderView.Stretch)

        self.settings = QSettings("MeWa", "ERP")
        self._restore_column_visibility()

        layout.addWidget(self.cari_table)

    def load_cari_list(self, filter_text: str = ""):
        query = """
            SELECT
                cari_kodu,
                firma_unvani,
                yetkili,
                telefon,
                sehir,
                ulke
            FROM cariler
        """

        params = []
        if filter_text.strip():
            keyword = f"%{filter_text.strip()}%"
            query += """
                WHERE
                    LOWER(cari_kodu) LIKE ? OR
                    LOWER(firma_unvani) LIKE ? OR
                    LOWER(yetkili) LIKE ? OR
                    LOWER(telefon) LIKE ? OR
                    LOWER(sehir) LIKE ? OR
                    LOWER(ulke) LIKE ?
            """
            params = [keyword.lower() for _ in range(6)]

        query += " ORDER BY firma_unvani"

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(query, params)
        veriler = cursor.fetchall()
        conn.close()

        self.cari_table.setRowCount(len(veriler))

        for satir, veri in enumerate(veriler):
            for sutun, deger in enumerate(veri):
                self.cari_table.setItem(
                    satir,
                    sutun,
                    QTableWidgetItem("" if deger is None else str(deger)),
                )

        self._update_statistics(veriler)

    def _update_statistics(self, veriler):
        toplam_cari = len(veriler)
        firma_sayisi = len({veri[1] for veri in veriler if veri[1]})
        sehir_sayisi = len({veri[4] for veri in veriler if veri[4]})
        ulke_sayisi = len({veri[5] for veri in veriler if veri[5]})

        self.stats_cards[0][1].setText(str(toplam_cari))
        self.stats_cards[1][1].setText(str(firma_sayisi))
        self.stats_cards[2][1].setText(str(sehir_sayisi))
        self.stats_cards[3][1].setText(str(ulke_sayisi))

    def _handle_search(self, text: str):
        self.load_cari_list(text)

    def _show_column_menu(self):
        menu = QMenu(self)
        for index, label in enumerate(self.column_labels):
            action = QAction(label, self)
            action.setCheckable(True)
            action.setChecked(not self.cari_table.isColumnHidden(index))
            action.triggered.connect(lambda checked, col=index: self._set_column_visibility(col, checked))
            menu.addAction(action)
        menu.exec_(self.toolbar.mapToGlobal(self.toolbar.rect().bottomLeft()))

    def _set_column_visibility(self, column_index, visible):
        self.cari_table.setColumnHidden(column_index, not visible)
        self.settings.setValue(f"cari_columns/{column_index}", visible)

    def _restore_column_visibility(self):
        for index, _ in enumerate(self.column_labels):
            visible = self.settings.value(f"cari_columns/{index}", True)
            self.cari_table.setColumnHidden(index, not visible)

    def _yeni_cari_ekle(self):
        dialog = NewCariDialog()
        if dialog.exec():
            self.load_cari_list(self.search_input.text())

    def _export_to_excel(self):
        try:
            from openpyxl import Workbook  # type: ignore
        except ImportError:
            QMessageBox.critical(self, "Hata", "openpyxl yüklü değil. Lütfen pip install openpyxl ile kurun.")
            return

        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "Excel Dosyasını Kaydet",
            "Cari_Listesi.xlsx",
            "Excel Dosyaları (*.xlsx)",
        )
        if not save_path:
            return

        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Cari Listesi"

        headers = [
            "Cari Kodu",
            "Firma Ünvanı",
            "Yetkili",
            "Telefon",
            "Şehir",
            "Ülke",
        ]
        sheet.append(headers)

        for row in range(self.cari_table.rowCount()):
            values = []
            for col in range(self.cari_table.columnCount()):
                item = self.cari_table.item(row, col)
                values.append("" if item is None else item.text())
            sheet.append(values)

        workbook.save(save_path)
        QMessageBox.information(self, "Başarılı", "Excel dosyası başarıyla export edildi.")

    def _export_to_pdf(self):
        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "PDF Dosyasını Kaydet",
            "Cari_Listesi.pdf",
            "PDF Dosyaları (*.pdf)",
        )
        if not save_path:
            return

        printer = QPrinter(QPrinter.HighResolution)
        printer.setOutputFormat(QPrinter.PdfFormat)
        printer.setOutputFileName(save_path)
        printer.setPageSize(QPrinter.A4)
        printer.setOrientation(QPrinter.Portrait)
        printer.setDocName("Cari Listesi")

        painter = QPainter(printer)
        try:
            page_width = printer.pageRect(QPrinter.DevicePixel).width()
            page_height = printer.pageRect(QPrinter.DevicePixel).height()
            x_margin = 30
            y_margin = 30
            row_height = 20
            header_height = 28
            col_widths = []
            total_cols = self.cari_table.columnCount()
            for col in range(total_cols):
                col_widths.append(max(80, int((page_width - 2 * x_margin) / total_cols)))

            painter.setFont(self.font())
            painter.drawText(x_margin, y_margin, "Cari Listesi")
            y = y_margin + 24
            painter.drawLine(x_margin, y, page_width - x_margin, y)
            y += 8

            painter.setFont(self.font())
            for col, label in enumerate(self.column_labels):
                painter.drawText(x_margin + sum(col_widths[:col]), y, col_widths[col], header_height, Qt.AlignLeft | Qt.AlignVCenter, label)
            y += header_height
            painter.drawLine(x_margin, y, page_width - x_margin, y)
            y += 4

            for row in range(self.cari_table.rowCount()):
                if y + row_height > page_height - y_margin:
                    printer.newPage()
                    y = y_margin + 20
                    painter.drawText(x_margin, y_margin, "Cari Listesi")
                    y += 24
                    painter.drawLine(x_margin, y, page_width - x_margin, y)
                    y += 8
                    for col, label in enumerate(self.column_labels):
                        painter.drawText(x_margin + sum(col_widths[:col]), y, col_widths[col], header_height, Qt.AlignLeft | Qt.AlignVCenter, label)
                    y += header_height
                    painter.drawLine(x_margin, y, page_width - x_margin, y)
                    y += 4

                for col in range(total_cols):
                    item = self.cari_table.item(row, col)
                    text = "" if item is None else item.text()
                    painter.drawText(x_margin + sum(col_widths[:col]), y, col_widths[col], row_height, Qt.AlignLeft | Qt.AlignVCenter, text)
                y += row_height
        finally:
            painter.end()

        QMessageBox.information(self, "Başarılı", "PDF dosyası başarıyla export edildi.")

    def _print_table(self):
        printer = QPrinter(QPrinter.HighResolution)
        printer.setOutputFormat(QPrinter.NativeFormat)
        printer.setDocName("Cari Listesi")

        painter = QPainter(printer)
        try:
            painter.drawText(50, 50, "Cari Listesi")
        finally:
            painter.end()

    def _get_selected_cari_kodu(self):
        selected_row = self.cari_table.currentRow()
        if selected_row < 0:
            return None

        cari_kodu_item = self.cari_table.item(selected_row, 0)
        if cari_kodu_item is None:
            return None

        return cari_kodu_item.text().strip()

    def _show_context_menu(self, position):
        row = self.cari_table.rowAt(position.y())
        if row >= 0:
            self.cari_table.selectRow(row)

        menu = QMenu(self)

        duzenle_action = QAction("Düzenle", self)
        duzenle_action.triggered.connect(self.cari_ac)
        menu.addAction(duzenle_action)

        sil_action = QAction("Sil", self)
        sil_action.triggered.connect(self._sil_cari)
        menu.addAction(sil_action)

        menu.exec_(self.cari_table.viewport().mapToGlobal(position))

    def cari_ac(self):
        cari_kodu = self._get_selected_cari_kodu()
        if not cari_kodu:
            return

        dialog = NewCariDialog(cari_kodu)
        if dialog.exec():
            self.load_cari_list(self.search_input.text())

    def _sil_cari(self):
        cari_kodu = self._get_selected_cari_kodu()
        if not cari_kodu:
            return

        cevap = QMessageBox.question(
            self,
            "Silme Onayı",
            "Cari kaydı silinsin mi?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if cevap == QMessageBox.Yes:
            try:
                CariModel.sil(cari_kodu)
                self.load_cari_list(self.search_input.text())
            except Exception as exc:
                QMessageBox.critical(self, "Hata", f"Cari silinirken bir hata oluştu:\n{exc}")