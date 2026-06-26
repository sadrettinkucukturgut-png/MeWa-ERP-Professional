from pathlib import Path

from PySide6.QtCore import Qt, QSettings
from PySide6.QtGui import QAction, QTextDocument
from PySide6.QtPrintSupport import QPrintDialog, QPrinter
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

from models.stock_model import StockModel
from ui.new_stock_dialog import NewStockDialog


class StockListPage(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Stok Listesi")
        self.resize(1100, 620)
        self._setup_ui()
        self.load_stock_list()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        self.page_title = QLabel("📦 Stok Listesi")
        self.page_title.setAlignment(Qt.AlignCenter)
        self.page_title.setStyleSheet("font-size: 24px; font-weight: bold; padding: 6px 0;")
        layout.addWidget(self.page_title)

        search_label = QLabel("Ara:")
        search_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(search_label)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Stok Kodu, Barkod, Ürün Adı, Kategori, Marka veya Depo")
        self.search_input.textChanged.connect(self._handle_search)
        layout.addWidget(self.search_input)

        self.toolbar = QToolBar()
        self.toolbar.setMovable(False)
        layout.addWidget(self.toolbar)

        self.action_yeni_stok = QAction("➕ Yeni Stok", self)
        self.action_yeni_stok.triggered.connect(self._yeni_stok_ekle)
        self.toolbar.addAction(self.action_yeni_stok)

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
            ("Toplam Stok", "📦"),
            ("Kritik Stok", "⚠"),
            ("Depo Sayısı", "🏭"),
            ("Toplam Değer", "💰"),
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

        self.stok_table = QTableWidget()
        self.stok_table.setObjectName("stokTable")
        self.column_labels = [
            "Stok Kodu",
            "Barkod",
            "Ürün Adı",
            "Kategori",
            "Marka",
            "Birim",
            "Alış Fiyatı",
            "Satış Fiyatı",
            "Mevcut Stok",
            "Kritik Stok",
            "Depo",
        ]
        self.stok_table.setColumnCount(len(self.column_labels))
        self.stok_table.setHorizontalHeaderLabels(self.column_labels)
        self.stok_table.setAlternatingRowColors(True)
        self.stok_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.stok_table.setSelectionMode(QTableWidget.SingleSelection)
        self.stok_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.stok_table.setSortingEnabled(False)
        self.stok_table.verticalHeader().setVisible(False)
        self.stok_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.stok_table.doubleClicked.connect(self.stok_ac)
        self.stok_table.customContextMenuRequested.connect(self._show_context_menu)

        header = self.stok_table.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(QHeaderView.Stretch)

        self.settings = QSettings("MeWa", "ERP")
        self._restore_column_visibility()
        layout.addWidget(self.stok_table)

    def load_stock_list(self, filter_text: str = ""):
        query = """
            SELECT
                stock_code,
                barcode,
                product_name,
                category,
                brand,
                unit,
                purchase_price,
                purchase_currency,
                sale_price,
                sale_currency,
                current_stock,
                critical_stock,
                warehouse
            FROM stoklar
        """

        params = []
        if filter_text.strip():
            keyword = f"%{filter_text.strip()}%"
            query += """
                WHERE
                    LOWER(stock_code) LIKE ? OR
                    LOWER(barcode) LIKE ? OR
                    LOWER(product_name) LIKE ? OR
                    LOWER(category) LIKE ? OR
                    LOWER(brand) LIKE ? OR
                    LOWER(warehouse) LIKE ? OR
                    LOWER(COALESCE(purchase_currency, '')) LIKE ? OR
                    LOWER(COALESCE(sale_currency, '')) LIKE ?
            """
            params = [keyword.lower() for _ in range(8)]

        query += " ORDER BY product_name"

        db_path = Path(__file__).resolve().parent.parent / "database" / "mewa.db"
        import sqlite3

        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            veriler = cursor.fetchall()

        self.stok_table.setRowCount(len(veriler))

        for satir, veri in enumerate(veriler):
            values = [
                veri[0],
                veri[1],
                veri[2],
                veri[3],
                veri[4],
                veri[5],
                self._format_price_value(veri[6], veri[7]),
                self._format_price_value(veri[8], veri[9]),
                veri[10],
                veri[11],
                veri[12],
            ]
            for sutun, deger in enumerate(values):
                self.stok_table.setItem(
                    satir,
                    sutun,
                    QTableWidgetItem("" if deger is None else str(deger)),
                )

        self._update_statistics(veriler)

    def _update_statistics(self, veriler):
        toplam_stok = len(veriler)
        kritik_stok = sum(1 for veri in veriler if veri[11] and veri[10] is not None and float(veri[10]) <= float(veri[11]))
        depo_sayisi = len({veri[12] for veri in veriler if veri[12]})
        toplam_deger = sum(
            float(veri[10] or 0) * float(veri[8] or 0)
            for veri in veriler
            if veri[10] is not None and veri[8] is not None
        )

        self.stats_cards[0][1].setText(str(toplam_stok))
        self.stats_cards[1][1].setText(str(kritik_stok))
        self.stats_cards[2][1].setText(str(depo_sayisi))
        self.stats_cards[3][1].setText(f"{toplam_deger:,.2f} USD")

    def _handle_search(self, text: str):
        self.load_stock_list(text)

    def _yeni_stok_ekle(self):
        dialog = NewStockDialog()
        if dialog.exec():
            self.load_stock_list(self.search_input.text())

    def _get_selected_stock_code(self):
        selected_row = self.stok_table.currentRow()
        if selected_row < 0:
            return None

        stock_code_item = self.stok_table.item(selected_row, 0)
        if stock_code_item is None:
            return None

        return stock_code_item.text().strip()

    def _show_context_menu(self, position):
        row = self.stok_table.rowAt(position.y())
        if row >= 0:
            self.stok_table.selectRow(row)

        menu = QMenu(self)
        duzenle_action = QAction("Düzenle", self)
        duzenle_action.triggered.connect(self.stok_ac)
        menu.addAction(duzenle_action)

        sil_action = QAction("Sil", self)
        sil_action.triggered.connect(self._sil_stok)
        menu.addAction(sil_action)

        menu.exec_(self.stok_table.viewport().mapToGlobal(position))

    def stok_ac(self):
        stock_code = self._get_selected_stock_code()
        if not stock_code:
            return

        dialog = NewStockDialog(stock_code)
        if dialog.exec():
            self.load_stock_list(self.search_input.text())

    def _sil_stok(self):
        stock_code = self._get_selected_stock_code()
        if not stock_code:
            return

        cevap = QMessageBox.question(
            self,
            "Silme Onayı",
            "Stok kaydı silinsin mi?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if cevap == QMessageBox.Yes:
            try:
                StockModel.sil(stock_code)
                self.load_stock_list(self.search_input.text())
            except Exception as exc:
                QMessageBox.critical(self, "Hata", f"Stok silinirken bir hata oluştu:\n{exc}")

    def _export_to_excel(self):
        try:
            from openpyxl import Workbook  # type: ignore
        except ImportError:
            QMessageBox.critical(self, "Hata", "openpyxl yüklü değil. Lütfen pip install openpyxl ile kurun.")
            return

        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "Excel Dosyasını Kaydet",
            "Stok_Listesi.xlsx",
            "Excel Dosyaları (*.xlsx)",
        )
        if not save_path:
            return

        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Stok Listesi"

        headers = [
            "Stok Kodu",
            "Barkod",
            "Ürün Adı",
            "Kategori",
            "Marka",
            "Birim",
            "Alış Fiyatı",
            "Satış Fiyatı",
            "Mevcut Stok",
            "Kritik Stok",
            "Depo",
        ]
        sheet.append(headers)

        for row in range(self.stok_table.rowCount()):
            values = []
            for col in range(self.stok_table.columnCount()):
                item = self.stok_table.item(row, col)
                values.append("" if item is None else item.text())
            sheet.append(values)

        workbook.save(save_path)
        QMessageBox.information(self, "Başarılı", "Excel dosyası başarıyla export edildi.")

    def _format_price_value(self, price, currency):
        if price in (None, ""):
            return ""
        try:
            return f"{float(price):,.2f} {currency or 'USD'}"
        except (TypeError, ValueError):
            return f"{price} {currency or 'USD'}"

    def _show_column_menu(self):
        menu = QMenu(self)
        for index, label in enumerate(self.column_labels):
            action = QAction(label, self)
            action.setCheckable(True)
            action.setChecked(not self.stok_table.isColumnHidden(index))
            action.triggered.connect(lambda checked, col=index: self._set_column_visibility(col, checked))
            menu.addAction(action)
        menu.exec_(self.toolbar.mapToGlobal(self.toolbar.rect().bottomLeft()))

    def _set_column_visibility(self, column_index, visible):
        self.stok_table.setColumnHidden(column_index, not visible)
        self.settings.setValue(f"stock_columns/{column_index}", visible)

    def _restore_column_visibility(self):
        for index, _ in enumerate(self.column_labels):
            visible = self.settings.value(f"stock_columns/{index}", True)
            self.stok_table.setColumnHidden(index, not visible)

    def _export_to_pdf(self):
        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "PDF Dosyasını Kaydet",
            "Stok_Listesi.pdf",
            "PDF Dosyaları (*.pdf)",
        )
        if not save_path:
            return

        printer = QPrinter(QPrinter.HighResolution)
        printer.setOutputFormat(QPrinter.PdfFormat)
        printer.setOutputFileName(save_path)
        self._print_document(printer)

    def _print_table(self):
        printer = QPrinter(QPrinter.HighResolution)
        dialog = QPrintDialog(printer, self)
        if dialog.exec_() != 0:
            return
        self._print_document(printer)

    def _print_document(self, printer):
        document = QTextDocument()
        document.setHtml(self._build_table_html())
        document.print(printer)

    def _build_table_html(self):
        visible_columns = []
        for index, label in enumerate(self.column_labels):
            if not self.stok_table.isColumnHidden(index):
                visible_columns.append(label)

        rows = []
        rows.append("<tr>" + "".join(f"<th>{label}</th>" for label in visible_columns) + "</tr>")

        for row in range(self.stok_table.rowCount()):
            cells = []
            for col, label in enumerate(self.column_labels):
                if self.stok_table.isColumnHidden(col):
                    continue
                item = self.stok_table.item(row, col)
                value = "" if item is None else item.text()
                cells.append(f"<td>{value}</td>")
            rows.append("<tr>" + "".join(cells) + "</tr>")

        return (
            "<html><body style='font-family:Arial; font-size:10px;'>"
            "<h2>Stok Listesi</h2>"
            f"<table border='1' cellspacing='0' cellpadding='4'>{''.join(rows)}</table>"
            "</body></html>"
        )
