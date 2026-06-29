from datetime import date
import os
import re
import tempfile
from urllib.parse import quote

from PySide6.QtCore import QDate, QEvent, QSettings, Qt, QUrl
from PySide6.QtGui import QAction, QCloseEvent, QDesktopServices
from PySide6.QtWidgets import (
    QDateEdit,
    QFrame,
    QGridLayout,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from models.stock_model import StockModel
from services.excel_service import ExcelService
from services.pdf_service import PDFService
from services.print_service import PrintService
from shared.widgets.stock_lookup_dialog import StockLookupDialog
from shared.widgets.table_column_state import add_layout_lock_toggle, apply_table_column_standard


class StockMovementRecordsPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Stok Hareket Kayıtları")
        self.resize(1280, 760)

        self.selected_stock = None
        self.selected_stock_id = 0
        self.selected_supplier = {}
        self.settings = QSettings("MeWa", "ERP")
        self._temp_pdf_files = set()

        self.column_labels = [
            "Tarih",
            "Belge Tipi",
            "Belge No",
            "Hareket Tipi",
            "Depo",
            "Giris Miktari",
            "Cikis Miktari",
            "Bakiye Miktari",
            "Birim",
            "Kullanici",
            "Aciklama",
            "Durum",
        ]

        self._setup_ui()
        self._show_empty_state()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        title = QLabel("📦 Stok Hareket Kayıtları")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size:24px; font-weight:bold; color:#e2e8f0; padding:6px 0;")
        main_layout.addWidget(title)

        search_frame = QFrame()
        search_frame.setStyleSheet("QFrame{background:#0f172a; border:1px solid #334155; border-radius:12px;}")
        search_layout = QGridLayout(search_frame)
        search_layout.setContentsMargins(14, 12, 14, 12)
        search_layout.setHorizontalSpacing(10)
        search_layout.setVerticalSpacing(8)

        self.stock_input = QLineEdit()
        self.stock_input.setReadOnly(True)
        self.stock_input.setPlaceholderText("Stok seciniz")
        self.stock_input.installEventFilter(self)

        self.stock_lookup_button = QPushButton("...")
        self.stock_lookup_button.setFixedWidth(32)
        self.stock_lookup_button.clicked.connect(self._open_stock_lookup)

        stock_row = QHBoxLayout()
        stock_row.setContentsMargins(0, 0, 0, 0)
        stock_row.setSpacing(6)
        stock_row.addWidget(self.stock_input, 1)
        stock_row.addWidget(self.stock_lookup_button, 0)

        stock_row_widget = QWidget()
        stock_row_widget.setLayout(stock_row)

        self.stock_code_input = QLineEdit()
        self.stock_code_input.setReadOnly(True)

        search_layout.addWidget(QLabel("Stok"), 0, 0)
        search_layout.addWidget(stock_row_widget, 0, 1)
        search_layout.addWidget(QLabel("Stok Kodu"), 1, 0)
        search_layout.addWidget(self.stock_code_input, 1, 1)

        self.start_date = QDateEdit()
        self.start_date.setCalendarPopup(True)
        first_day = date.today().replace(day=1)
        self.start_date.setDate(QDate(first_day.year, first_day.month, first_day.day))

        self.end_date = QDateEdit()
        self.end_date.setCalendarPopup(True)
        self.end_date.setDate(QDate.currentDate())

        self.load_button = QPushButton("Yukle")
        self.load_button.clicked.connect(self._load_ledger)

        search_layout.addWidget(QLabel("Baslangic Tarihi"), 0, 2)
        search_layout.addWidget(self.start_date, 0, 3)
        search_layout.addWidget(QLabel("Bitis Tarihi"), 1, 2)
        search_layout.addWidget(self.end_date, 1, 3)
        search_layout.addWidget(self.load_button, 0, 4, 2, 1)

        main_layout.addWidget(search_frame)

        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Filtre:"))
        self.grid_filter_input = QLineEdit()
        self.grid_filter_input.setPlaceholderText("Belge tipi, no, hareket tipi, depo, aciklama, durum...")
        self.grid_filter_input.textChanged.connect(self._filter_grid_rows)
        filter_row.addWidget(self.grid_filter_input, 1)
        main_layout.addLayout(filter_row)

        self.toolbar = QToolBar()
        self.toolbar.setMovable(False)
        main_layout.addWidget(self.toolbar)

        self.action_excel = QAction("📄 Excel", self)
        self.action_excel.triggered.connect(self._export_to_excel)
        self.toolbar.addAction(self.action_excel)

        self.action_pdf = QAction("🖨 PDF", self)
        self.action_pdf.triggered.connect(self._export_to_pdf)
        self.toolbar.addAction(self.action_pdf)

        self.action_print = QAction("🖨 Yazdir", self)
        self.action_print.triggered.connect(self._print_table)
        self.toolbar.addAction(self.action_print)

        self.action_whatsapp = QAction("🟢 WhatsApp", self)
        self.action_whatsapp.setEnabled(False)
        self.action_whatsapp.triggered.connect(self._open_whatsapp_with_statement)
        self.toolbar.addAction(self.action_whatsapp)

        self.toolbar.addSeparator()

        self.action_columns = QAction("⚙️ Kolonlar", self)
        self.action_columns.triggered.connect(self._show_column_menu)
        self.toolbar.addAction(self.action_columns)

        self.stack = QStackedWidget()
        self.empty_label = QLabel("Lutfen bir stok secin.")
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setStyleSheet("font-size:18px; font-weight:600; color:#94a3b8;")
        empty_page = QWidget()
        empty_layout = QVBoxLayout(empty_page)
        empty_layout.addStretch()
        empty_layout.addWidget(self.empty_label)
        empty_layout.addStretch()

        self.table = QTableWidget()
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSortingEnabled(True)
        self.table.setColumnCount(len(self.column_labels))
        self.table.setHorizontalHeaderLabels(self.column_labels)
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table.verticalHeader().setVisible(False)
        self.table.setWordWrap(True)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)

        table_page = QWidget()
        table_layout = QVBoxLayout(table_page)
        table_layout.setContentsMargins(0, 0, 0, 0)
        table_layout.addWidget(self.table)

        self.stack.addWidget(empty_page)
        self.stack.addWidget(table_page)
        main_layout.addWidget(self.stack)

        self._restore_column_visibility()
        apply_table_column_standard(
            self.table,
            self.settings,
            "stock_movement_records_table",
            keep_last_column_stretch=False,
        )
        self._apply_table_column_layout()

        self.action_layout_lock = add_layout_lock_toggle(
            self.toolbar,
            self.table,
            self.settings,
            "stock_movement_records_table",
            self,
            keep_last_column_stretch=False,
        )
        self.action_layout_lock.setText("🔓 Yerlesimi Ac" if self.action_layout_lock.isChecked() else "🔒 Yerlesimi Kilitle")
        self.action_layout_lock.toggled.connect(
            lambda checked: self.action_layout_lock.setText("🔓 Yerlesimi Ac" if checked else "🔒 Yerlesimi Kilitle")
        )

        bottom_frame = QFrame()
        bottom_frame.setStyleSheet(
            "QFrame{background:#0f172a; border:1px solid #334155; border-radius:12px;}"
        )
        bottom_layout = QHBoxLayout(bottom_frame)
        bottom_layout.setContentsMargins(12, 12, 12, 12)
        bottom_layout.setSpacing(12)

        self.summary_cards = {}
        for title_text, value in [
            ("Acilis Stogu", "0.000"),
            ("Toplam Giris", "0.000"),
            ("Toplam Cikis", "0.000"),
            ("Kapanis Stogu", "0.000"),
        ]:
            card = QFrame()
            card.setStyleSheet(
                "QFrame{background:#111827; border:1px solid #334155; border-radius:12px;}"
            )
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(14, 14, 14, 14)
            card_layout.setSpacing(6)

            value_label = QLabel(value)
            value_label.setStyleSheet("font-size:20px; font-weight:bold; color:#f8fafc;")
            title_label = QLabel(title_text)
            title_label.setStyleSheet("font-size:12px; color:#94a3b8;")

            card_layout.addWidget(value_label)
            card_layout.addWidget(title_label)
            bottom_layout.addWidget(card)
            self.summary_cards[title_text] = value_label

        main_layout.addWidget(bottom_frame)

        self.start_date.dateChanged.connect(lambda _d: self._load_ledger())
        self.end_date.dateChanged.connect(lambda _d: self._load_ledger())

        self.setStyleSheet(
            "QLabel{color:#e2e8f0;}"
            "QLineEdit,QDateEdit{background:#0f172a; color:#e2e8f0; border:1px solid #334155; border-radius:8px; padding:6px;}"
            "QPushButton{background:#1e293b; color:#f8fafc; border:1px solid #334155; border-radius:8px; padding:7px 12px;}"
            "QPushButton:hover{background:#334155;}"
            "QTableWidget{background:#111827; alternate-background-color:#0f172a; color:#e5e7eb; border:1px solid #334155;}"
            "QHeaderView::section{background:#1f2937; color:#e5e7eb; padding:8px 6px;}"
        )

    def eventFilter(self, watched, event):  # noqa: N802
        if watched is self.stock_input and event.type() == QEvent.MouseButtonDblClick:
            self._open_stock_lookup()
            return True
        return super().eventFilter(watched, event)

    def _show_empty_state(self):
        self.table.setRowCount(0)
        self.stack.setCurrentIndex(0)
        self.action_whatsapp.setEnabled(False)
        self.stock_input.clear()
        self.stock_code_input.clear()
        self.summary_cards["Acilis Stogu"].setText("0.000")
        self.summary_cards["Toplam Giris"].setText("0.000")
        self.summary_cards["Toplam Cikis"].setText("0.000")
        self.summary_cards["Kapanis Stogu"].setText("0.000")

    def _open_stock_lookup(self):
        selected = StockLookupDialog.select_stock(self)
        if selected is None:
            return

        self.selected_stock = selected
        self.selected_stock_id = int(selected.get("stock_id") or 0)

        # Clear previous stock result immediately for better UX.
        self.table.setRowCount(0)
        self.stack.setCurrentIndex(0)
        self.empty_label.setText("Stok hareketleri yukleniyor...")

        self.stock_input.setText(str(selected.get("product_name") or ""))
        self.stock_code_input.setText(str(selected.get("stock_code") or ""))

        self.selected_supplier = StockModel.resolve_supplier_for_stock(self.selected_stock_id)
        self.action_whatsapp.setEnabled(bool(self.stock_input.text().strip()))
        self._load_ledger()

    def _load_ledger(self):
        if self.selected_stock_id <= 0:
            self._show_empty_state()
            return

        start_date = self.start_date.date().toString("yyyy-MM-dd")
        end_date = self.end_date.date().toString("yyyy-MM-dd")
        if start_date > end_date:
            QMessageBox.warning(self, "Uyari", "Baslangic tarihi bitis tarihinden buyuk olamaz.")
            return

        ledger = StockModel.stock_movement_ledger(
            stock_id=self.selected_stock_id,
            start_date=start_date,
            end_date=end_date,
        )
        debug = ledger.get("debug", {})
        print(
            f"[StockMovementDebug] Selected Stock ID: {self.selected_stock_id} | "
            f"Selected Stock Code: {self.stock_code_input.text().strip()}"
        )
        if debug:
            print(f"[StockMovementDebug] SQL query: {debug.get('sql', '')}")
            print(
                "[StockMovementDebug] Returned row count: "
                f"stock_only={debug.get('stock_only_row_count', 0)}, "
                f"period={debug.get('period_row_count', 0)}"
            )
            print(
                "[StockMovementDebug] Backfill inserted rows: "
                f"purchase={debug.get('backfilled_purchase_rows', 0)}, "
                f"sales={debug.get('backfilled_sales_rows', 0)}"
            )
            if bool(debug.get("date_filter_warning", False)):
                print("[StockMovementDebug] Date filter warning: stock rows exist but period rows are zero.")
        rows = ledger.get("rows", [])

        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            values = [
                str(row.get("date") or ""),
                str(row.get("document_type") or ""),
                str(row.get("document_no") or ""),
                str(row.get("movement_type") or ""),
                str(row.get("warehouse") or ""),
                f"{float(row.get('in_qty') or 0):,.3f}",
                f"{float(row.get('out_qty') or 0):,.3f}",
                f"{float(row.get('balance_qty') or 0):,.3f}",
                str(row.get("unit") or ""),
                str(row.get("user") or "SYSTEM"),
                str(row.get("description") or ""),
                str(row.get("status") or ""),
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                if col in (5, 6, 7):
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                if col == 10:
                    item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                self.table.setItem(row_index, col, item)

        self.table.setSortingEnabled(True)
        self._apply_table_column_layout()

        if not rows:
            self.empty_label.setText("Seçilen dönem için stok hareketi bulunamadı.")
            self.stack.setCurrentIndex(0)
        else:
            self.stack.setCurrentIndex(1)

        self._filter_grid_rows(self.grid_filter_input.text())

        self.summary_cards["Acilis Stogu"].setText(f"{float(ledger.get('opening_stock') or 0):,.3f}")
        self.summary_cards["Toplam Giris"].setText(f"{float(ledger.get('total_in') or 0):,.3f}")
        self.summary_cards["Toplam Cikis"].setText(f"{float(ledger.get('total_out') or 0):,.3f}")
        self.summary_cards["Kapanis Stogu"].setText(f"{float(ledger.get('closing_stock') or 0):,.3f}")

    def _filter_grid_rows(self, text: str):
        token = (text or "").strip().lower()
        for row in range(self.table.rowCount()):
            if not token:
                self.table.setRowHidden(row, False)
                continue
            haystack = " ".join(
                (self.table.item(row, col).text() if self.table.item(row, col) else "")
                for col in range(self.table.columnCount())
            ).lower()
            self.table.setRowHidden(row, token not in haystack)

    def _show_column_menu(self):
        menu = QMenu(self)
        for index, label in enumerate(self.column_labels):
            action = QAction(label, self)
            action.setCheckable(True)
            action.setChecked(not self.table.isColumnHidden(index))
            action.triggered.connect(lambda checked, col=index: self._set_column_visibility(col, checked))
            menu.addAction(action)
        menu.exec_(self.toolbar.mapToGlobal(self.toolbar.rect().bottomLeft()))

    def _set_column_visibility(self, index: int, visible: bool):
        self.table.setColumnHidden(index, not visible)
        self.settings.setValue(f"stock_movement_records_columns/{index}", bool(visible))
        self._apply_table_column_layout()

    def _restore_column_visibility(self):
        for index, _ in enumerate(self.column_labels):
            value = self.settings.value(f"stock_movement_records_columns/{index}", True)
            if value is None:
                value = self.settings.value(f"stock_movement_ledger_columns/{index}", True)
            if isinstance(value, str):
                visible = value.lower() == "true"
            else:
                visible = bool(value)
            self.table.setColumnHidden(index, not visible)

    def _apply_table_column_layout(self):
        header = self.table.horizontalHeader()
        for col in range(self.table.columnCount()):
            if col == 10:
                continue
            header.setSectionResizeMode(col, QHeaderView.Interactive)

        # Description is always the widest and stretches to occupy remaining width.
        header.setSectionResizeMode(10, QHeaderView.Stretch)

        # Small columns
        self.table.setColumnWidth(0, 110)   # Date
        self.table.setColumnWidth(11, 100)  # Status
        self.table.setColumnWidth(9, 90)    # User

        # Medium columns
        self.table.setColumnWidth(1, 160)   # Document Type
        self.table.setColumnWidth(2, 170)   # Document No
        self.table.setColumnWidth(3, 180)   # Movement Type
        self.table.setColumnWidth(4, 150)   # Warehouse
        self.table.setColumnWidth(8, 90)    # Unit

        # Numeric columns
        self.table.setColumnWidth(5, 110)   # In Qty
        self.table.setColumnWidth(6, 110)   # Out Qty
        self.table.setColumnWidth(7, 120)   # Balance Qty

        # Keep description highly visible even before stretch kicks in.
        self.table.setColumnWidth(10, 480)

    def _visible_headers_and_rows(self):
        headers = [self.column_labels[col] for col in range(self.table.columnCount()) if not self.table.isColumnHidden(col)]
        rows = []
        for row in range(self.table.rowCount()):
            if self.table.isRowHidden(row):
                continue
            values = []
            for col in range(self.table.columnCount()):
                if self.table.isColumnHidden(col):
                    continue
                item = self.table.item(row, col)
                values.append("" if item is None else item.text())
            rows.append(values)
        return headers, rows

    def _build_pdf_payload(self):
        headers, rows = self._visible_headers_and_rows()
        stock_code = self.stock_code_input.text().strip()
        stock_name = self.stock_input.text().strip()
        date_range = f"{self.start_date.date().toString('yyyy-MM-dd')} - {self.end_date.date().toString('yyyy-MM-dd')}"

        if not headers:
            headers = list(self.column_labels)

        row_width = max(1, len(headers))

        def meta_row(label: str, value: str) -> list[str]:
            row = ["" for _ in range(row_width)]
            row[0] = f"{label}: {value}"
            return row

        printable_rows = [
            meta_row("Stok", stock_name),
            meta_row("Stok Kodu", stock_code),
            meta_row("Tarih Araligi", date_range),
            meta_row("Uretim Tarihi", QDate.currentDate().toString("yyyy-MM-dd")),
            ["" for _ in range(row_width)],
        ]

        for source_row in rows:
            padded = list(source_row[:row_width])
            if len(padded) < row_width:
                padded.extend([""] * (row_width - len(padded)))
            printable_rows.append(padded)

        printable_rows.extend(
            [
                ["" for _ in range(row_width)],
                meta_row("Acilis Stogu", self.summary_cards["Acilis Stogu"].text()),
                meta_row("Toplam Giris", self.summary_cards["Toplam Giris"].text()),
                meta_row("Toplam Cikis", self.summary_cards["Toplam Cikis"].text()),
                meta_row("Kapanis Stogu", self.summary_cards["Kapanis Stogu"].text()),
            ]
        )

        title = f"Stok Hareket Kayıtları - {stock_code} - {stock_name} - {date_range}".strip(" -")
        return headers, printable_rows, title

    def _export_to_excel(self):
        headers, rows = self._visible_headers_and_rows()
        ExcelService.export_excel(
            self,
            headers,
            rows,
            "Stok_Hareket_Kayıtları.xlsx",
            sheet_title="Stok Hareket Kayıtları",
            success_message="Excel dosyasi basariyla disari aktarildi.",
        )

    def _export_to_pdf(self):
        headers, rows, title = self._build_pdf_payload()
        PDFService.generate_pdf(
            self,
            headers,
            rows,
            "Stock_Movement_Statement.pdf",
            title,
        )

    def _print_table(self):
        headers, rows = self._visible_headers_and_rows()
        PrintService.print_report(self, headers, rows, "Stok Hareket Kayıtları")

    def _show_context_menu(self, pos):
        row = self.table.rowAt(pos.y())
        if row >= 0:
            self.table.selectRow(row)

        menu = QMenu(self)
        info_action = QAction("Kaynak belge ayrintisi henuz mevcut degil.", self)
        info_action.setEnabled(False)
        menu.addAction(info_action)
        menu.exec_(self.table.viewport().mapToGlobal(pos))

    def _open_whatsapp_with_statement(self):
        if not self.stock_input.text().strip() or self.selected_stock_id <= 0:
            QMessageBox.warning(self, "Uyari", "Lutfen once bir stok secin.")
            return

        headers, rows, title = self._build_pdf_payload()

        self._cleanup_temp_pdfs()
        try:
            temp_file = tempfile.NamedTemporaryFile(prefix="mewa_stock_statement_", suffix=".pdf", delete=False)
            temp_pdf_path = temp_file.name
            temp_file.close()
        except Exception as exc:
            QMessageBox.critical(self, "Hata", f"PDF dosyasi hazirlanamadi:\n{exc}")
            return

        ok, error_message = PDFService.generate_pdf_to_path(
            headers=headers,
            rows=rows,
            save_path=temp_pdf_path,
            title=title,
        )
        if not ok:
            try:
                if os.path.exists(temp_pdf_path):
                    os.remove(temp_pdf_path)
            except OSError:
                pass
            QMessageBox.critical(self, "Hata", f"PDF olusturma hatasi:\n{error_message}")
            return

        self._temp_pdf_files.add(temp_pdf_path)

        phone = self._selected_supplier_whatsapp_phone()
        normalized_phone = self._normalize_phone_for_whatsapp(phone)
        if not normalized_phone:
            QMessageBox.information(
                self,
                "Bilgi",
                "Secilen stok icin tedarikci WhatsApp numarasi bulunamadi. PDF hazir:\n"
                f"{temp_pdf_path}",
            )
            return

        default_message = (
            "Merhaba,\n\n"
            "Stok hareket kayitlari ekstresi ektedir.\n\n"
            "Iyi calismalar,\n"
            "MeWa Automotive"
        )
        encoded_message = quote(default_message)
        encoded_path = quote(temp_pdf_path)

        desktop_url = QUrl(f"whatsapp://send?phone={normalized_phone}&text={encoded_message}&attachment={encoded_path}")
        opened = QDesktopServices.openUrl(desktop_url)
        if not opened:
            web_url = QUrl(f"https://web.whatsapp.com/send?phone={normalized_phone}&text={encoded_message}&attachment={encoded_path}")
            opened = QDesktopServices.openUrl(web_url)

        if not opened:
            QMessageBox.warning(self, "Uyari", "WhatsApp acilamadi.")
            return

        QMessageBox.information(
            self,
            "Bilgi",
            "WhatsApp konusmasi hazirlandi. PDF dosya yolu:\n"
            f"{temp_pdf_path}\n\n"
            "Mesaji kontrol edip Gonder'e basin.",
        )

    def _selected_supplier_whatsapp_phone(self) -> str:
        if self.selected_supplier:
            phone = str(self.selected_supplier.get("whatsapp") or "").strip()
            if phone:
                return phone
            phone = str(self.selected_supplier.get("phone") or "").strip()
            if phone:
                return phone
        return ""

    def _normalize_phone_for_whatsapp(self, value: str) -> str:
        raw = str(value or "").strip()
        if not raw:
            return ""

        normalized = re.sub(r"[^\d+]", "", raw)
        if normalized.startswith("+"):
            normalized = normalized[1:]
        if normalized.startswith("00"):
            normalized = normalized[2:]

        if normalized.startswith("0") and len(normalized) == 11:
            normalized = "90" + normalized[1:]
        elif len(normalized) == 10:
            normalized = "90" + normalized

        if len(normalized) < 10:
            return ""
        return normalized

    def _cleanup_temp_pdfs(self):
        for path in list(self._temp_pdf_files):
            try:
                if os.path.exists(path):
                    os.remove(path)
            except OSError:
                pass
            finally:
                self._temp_pdf_files.discard(path)

    def closeEvent(self, event: QCloseEvent):  # noqa: N802
        self._cleanup_temp_pdfs()
        super().closeEvent(event)
