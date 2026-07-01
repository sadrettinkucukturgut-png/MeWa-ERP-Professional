from datetime import date
import os
import re
import tempfile
from urllib.parse import quote

from PySide6.QtCore import QDate, QEvent, QSettings, Qt
from PySide6.QtGui import QAction, QCloseEvent, QDesktopServices
from PySide6.QtCore import QUrl
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

from models.purchase_invoice_model import PurchaseInvoiceModel
from models.cari_model import CariModel
from models.finance_model import FinanceModel
from services.excel_service import ExcelService
from services.pdf_service import PDFService
from services.print_service import PrintService
from shared.widgets.cari_lookup_dialog import CariLookupDialog
from shared.widgets.table_column_state import add_layout_lock_toggle, apply_table_column_standard
from ui.new_purchase_invoice_dialog import NewPurchaseInvoiceDialog


class CariHareketleriDialog(QWidget):
    def __init__(self, cari_kodu=None, firma_unvani="", bakiye=0.0, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Cari Hareket Kayıtları")
        self.resize(1280, 760)

        self.cari_kodu = cari_kodu or ""
        self.firma_unvani = firma_unvani or ""
        self.bakiye = bakiye
        self.selected_cari = None
        self.selected_supplier_id = 0
        self.settings = QSettings("MeWa", "ERP")
        self._temp_pdf_files = set()
        self._listener = self._on_finance_changed
        FinanceModel.register_listener(self._listener)

        self.column_labels = [
            "Tarih",
            "Belge Tipi",
            "Belge No",
            "Açıklama",
            "Borç",
            "Alacak",
            "Bakiye",
            "Para Birimi",
            "Kullanıcı",
            "Durum",
        ]

        self._setup_ui()
        self._show_empty_state()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        title = QLabel("📄 Cari Hareket Kayıtları")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size:24px; font-weight:bold; color:#e2e8f0; padding:6px 0;")
        main_layout.addWidget(title)

        search_frame = QFrame()
        search_frame.setStyleSheet("QFrame{background:#0f172a; border:1px solid #334155; border-radius:12px;}")
        search_layout = QGridLayout(search_frame)
        search_layout.setContentsMargins(10, 8, 10, 8)
        search_layout.setHorizontalSpacing(10)
        search_layout.setVerticalSpacing(6)

        self.customer_input = QLineEdit()
        self.customer_input.setReadOnly(True)
        self.customer_input.setPlaceholderText("Müşteri seçiniz")
        self.customer_input.installEventFilter(self)

        self.customer_lookup_button = QPushButton("...")
        self.customer_lookup_button.setFixedWidth(32)
        self.customer_lookup_button.clicked.connect(self._open_customer_lookup)

        customer_row = QHBoxLayout()
        customer_row.setContentsMargins(0, 0, 0, 0)
        customer_row.setSpacing(6)
        customer_row.addWidget(self.customer_input, 1)
        customer_row.addWidget(self.customer_lookup_button, 0)

        customer_row_widget = QWidget()
        customer_row_widget.setLayout(customer_row)

        self.customer_code_input = QLineEdit()
        self.customer_code_input.setReadOnly(True)

        self.company_name_input = QLineEdit()
        self.company_name_input.setReadOnly(True)

        self.current_balance_input = QLineEdit()
        self.current_balance_input.setReadOnly(True)

        search_layout.addWidget(QLabel("Müşteri"), 0, 0)
        search_layout.addWidget(customer_row_widget, 0, 1)
        search_layout.addWidget(QLabel("Müşteri Kodu"), 1, 0)
        search_layout.addWidget(self.customer_code_input, 1, 1)
        search_layout.addWidget(QLabel("Firma Ünvanı"), 2, 0)
        search_layout.addWidget(self.company_name_input, 2, 1)
        search_layout.addWidget(QLabel("Güncel Bakiye"), 3, 0)
        search_layout.addWidget(self.current_balance_input, 3, 1)

        self.start_date = QDateEdit()
        self.start_date.setCalendarPopup(True)
        first_day = date.today().replace(month=1, day=1)
        self.start_date.setDate(QDate(first_day.year, first_day.month, first_day.day))

        self.end_date = QDateEdit()
        self.end_date.setCalendarPopup(True)
        today = QDate.currentDate()
        self.end_date.setDate(today)

        self.load_button = QPushButton("Yükle")
        self.load_button.clicked.connect(self._load_ledger)

        search_layout.addWidget(QLabel("Başlangıç Tarihi"), 0, 2)
        search_layout.addWidget(self.start_date, 0, 3)
        search_layout.addWidget(QLabel("Bitiş Tarihi"), 1, 2)
        search_layout.addWidget(self.end_date, 1, 3)
        search_layout.addWidget(self.load_button, 2, 3)
        search_frame.setMaximumHeight(138)

        main_layout.addWidget(search_frame)

        self.grid_filter_input = QLineEdit()
        self.grid_filter_input.setVisible(False)

        self.toolbar = QToolBar()
        self.toolbar.setMovable(False)
        main_layout.addWidget(self.toolbar)

        self.action_excel = QAction("📄 Excel", self)
        self.action_excel.triggered.connect(self._export_to_excel)
        self.toolbar.addAction(self.action_excel)

        self.action_pdf = QAction("🖨 PDF", self)
        self.action_pdf.triggered.connect(self._export_to_pdf)
        self.toolbar.addAction(self.action_pdf)

        self.action_print = QAction("🖨 Yazdır", self)
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
        self.empty_label = QLabel("Please select a customer.")
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
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        self.table.doubleClicked.connect(self._open_source_document)
        self.table.horizontalHeader().sortIndicatorChanged.connect(self._save_sorting_state)

        table_page = QWidget()
        table_layout = QVBoxLayout(table_page)
        table_layout.setContentsMargins(0, 0, 0, 0)
        table_layout.setSpacing(0)
        table_layout.addWidget(self.table)

        self.stack.addWidget(empty_page)
        self.stack.addWidget(table_page)
        main_layout.addWidget(self.stack)

        self._restore_column_visibility()
        apply_table_column_standard(
            self.table,
            self.settings,
            "customer_ledger_table",
            keep_last_column_stretch=False,
        )
        self._restore_sorting_state()

        self.action_layout_lock = add_layout_lock_toggle(
            self.toolbar,
            self.table,
            self.settings,
            "customer_ledger_table",
            self,
            keep_last_column_stretch=False,
        )
        self.action_layout_lock.setText("🔓 Unlock Layout" if self.action_layout_lock.isChecked() else "🔒 Lock Layout")
        self.action_layout_lock.toggled.connect(
            lambda checked: self.action_layout_lock.setText("🔓 Unlock Layout" if checked else "🔒 Lock Layout")
        )

        bottom_frame = QFrame()
        bottom_frame.setStyleSheet(
            "QFrame{background:#0f172a; border:1px solid #334155; border-radius:12px;}"
        )
        bottom_layout = QHBoxLayout(bottom_frame)
        bottom_layout.setContentsMargins(12, 12, 12, 12)
        bottom_layout.setSpacing(12)

        self.summary_cards = {}
        for title, value in [
            ("Açılış Bakiye", "0.00"),
            ("Toplam Borç", "0.00"),
            ("Toplam Alacak", "0.00"),
            ("Kapanış Bakiye", "0.00"),
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
            title_label = QLabel(title)
            title_label.setStyleSheet("font-size:12px; color:#94a3b8;")

            card_layout.addWidget(value_label)
            card_layout.addWidget(title_label)
            bottom_layout.addWidget(card, 1)
            self.summary_cards[title] = value_label

        bottom_frame.setFixedHeight(110)
        main_layout.addWidget(bottom_frame)
        main_layout.setStretchFactor(self.stack, 1)

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
        if watched is self.customer_input and event.type() == QEvent.MouseButtonDblClick:
            self._open_customer_lookup()
            return True
        return super().eventFilter(watched, event)

    def _show_empty_state(self):
        self.table.setRowCount(0)
        self.stack.setCurrentIndex(0)
        self.action_whatsapp.setEnabled(False)
        self.summary_cards["Açılış Bakiye"].setText("0.00")
        self.summary_cards["Toplam Borç"].setText("0.00")
        self.summary_cards["Toplam Alacak"].setText("0.00")
        self.summary_cards["Kapanış Bakiye"].setText("0.00")

    def _open_customer_lookup(self):
        selected = CariLookupDialog.select_cari(self)
        if selected is None:
            return

        self.selected_cari = selected
        self.customer_input.setText(str(selected.get("firma_unvani") or ""))
        self.customer_code_input.setText(str(selected.get("cari_kodu") or ""))
        self.company_name_input.setText(str(selected.get("firma_unvani") or selected.get("company_name") or ""))
        self.selected_supplier_id = int(selected.get("supplier_id") or 0)
        if self.selected_supplier_id <= 0:
            self.selected_supplier_id = PurchaseInvoiceModel.resolve_supplier_id_for_cari(
                cari_kodu=self.customer_code_input.text().strip(),
                firma_unvani=self.company_name_input.text().strip(),
            )

        current_balance = PurchaseInvoiceModel.current_balance_for_supplier(self.selected_supplier_id)
        self._set_current_balance_display(current_balance, "USD")
        self.action_whatsapp.setEnabled(bool(self.customer_input.text().strip()))
        self._load_ledger()

    def _set_current_balance_display(self, balance: float, currency: str):
        curr = str(currency or "USD").strip().upper() or "USD"
        if balance > 0:
            self.current_balance_input.setText(f"{balance:,.2f} {curr} (ALACAKLIYIZ)")
            self.current_balance_input.setStyleSheet("color:#16a34a; font-weight:700;")
        elif balance < 0:
            self.current_balance_input.setText(f"{abs(balance):,.2f} {curr} (BORÇLUYUZ)")
            self.current_balance_input.setStyleSheet("color:#dc2626; font-weight:700;")
        else:
            self.current_balance_input.setText(f"BAKIYE YOK (0.00 {curr})")
            self.current_balance_input.setStyleSheet("color:#94a3b8; font-weight:700;")

    def _load_ledger(self):
        if self.selected_supplier_id <= 0:
            self._show_empty_state()
            return

        start_date = self.start_date.date().toString("yyyy-MM-dd")
        end_date = self.end_date.date().toString("yyyy-MM-dd")
        if start_date > end_date:
            QMessageBox.warning(self, "Uyarı", "Başlangıç tarihi bitiş tarihinden büyük olamaz.")
            return

        ledger = PurchaseInvoiceModel.ledger_for_supplier(
            supplier_id=self.selected_supplier_id,
            start_date=start_date,
            end_date=end_date,
        )
        rows = ledger.get("rows", [])

        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            description_value = self._display_description(row)
            values = [
                str(row.get("date") or ""),
                str(row.get("document_type") or ""),
                str(row.get("document_no") or ""),
                description_value,
                f"{float(row.get('debit') or 0):,.2f}",
                f"{float(row.get('credit') or 0):,.2f}",
                f"{float(row.get('running_balance') or 0):,.2f}",
                str(row.get("currency") or "USD"),
                str(row.get("user") or "SYSTEM"),
                str(row.get("status") or ""),
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                if col in (4, 5, 6):
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.table.setItem(row_index, col, item)

            self.table.item(row_index, 0).setData(Qt.UserRole, row)

        self.table.setSortingEnabled(True)
        self.stack.setCurrentIndex(1)
        self._filter_grid_rows(self.grid_filter_input.text())

        self.summary_cards["Açılış Bakiye"].setText(f"{float(ledger.get('opening_balance') or 0):,.2f}")
        self.summary_cards["Toplam Borç"].setText(f"{float(ledger.get('total_debit') or 0):,.2f}")
        self.summary_cards["Toplam Alacak"].setText(f"{float(ledger.get('total_credit') or 0):,.2f}")
        self.summary_cards["Kapanış Bakiye"].setText(f"{float(ledger.get('closing_balance') or 0):,.2f}")
        self._set_current_balance_display(PurchaseInvoiceModel.current_balance_for_supplier(self.selected_supplier_id), "USD")

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

    def _on_finance_changed(self, _event: str):
        if self.selected_supplier_id > 0:
            self._load_ledger()

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
        self.settings.setValue(f"customer_ledger_columns/{index}", bool(visible))

    def _restore_column_visibility(self):
        for index, _ in enumerate(self.column_labels):
            value = self.settings.value(f"customer_ledger_columns/{index}", True)
            if isinstance(value, str):
                visible = value.lower() == "true"
            else:
                visible = bool(value)
            self.table.setColumnHidden(index, not visible)

    def _save_sorting_state(self, column: int, order):
        self.settings.setValue("customer_ledger_sort/column", int(column))
        order_value = getattr(order, "value", order)
        self.settings.setValue("customer_ledger_sort/order", int(order_value))

    def _restore_sorting_state(self):
        try:
            column_value = self.settings.value("customer_ledger_sort/column", 0)
            default_order_value = getattr(Qt.SortOrder.AscendingOrder, "value", 0)
            order_value = self.settings.value("customer_ledger_sort/order", default_order_value)

            column = int(column_value)
            order = Qt.SortOrder(int(order_value))
        except Exception as e:
            print(f"Customer Ledger layout restore error: {e}")
            return
        if 0 <= column < self.table.columnCount():
            try:
                self.table.sortItems(column, order)
            except Exception as e:
                print(f"Customer Ledger sort apply error: {e}")

    def _display_description(self, row):
        document_type = str(row.get("document_type") or "")
        document_no = str(row.get("document_no") or "")
        original = str(row.get("description") or "")

        if document_type == "Alış Faturası":
            return f"Alış Faturası {document_no}".strip()

        if original.lower().startswith("purchase invoice") and document_no:
            return f"Alış Faturası {document_no}"

        return original

    def _show_context_menu(self, pos):
        row = self.table.rowAt(pos.y())
        if row >= 0:
            self.table.selectRow(row)

        menu = QMenu(self)
        open_action = QAction("Belgeyi Aç", self)
        open_action.triggered.connect(self._open_source_document)
        menu.addAction(open_action)
        menu.exec_(self.table.viewport().mapToGlobal(pos))

    def _open_source_document(self):
        row = self.table.currentRow()
        if row < 0:
            return
        date_item = self.table.item(row, 0)
        if date_item is None:
            return
        payload = date_item.data(Qt.UserRole) or {}
        document_type = str(payload.get("document_type") or "")
        document_no = str(payload.get("document_no") or "")

        if document_type == "Alış Faturası" and document_no:
            dialog = NewPurchaseInvoiceDialog(invoice_number=document_no, parent=self)
            dialog.exec()
            return

        QMessageBox.information(self, "Bilgi", "Kaynak belge bu modülde görüntülenemiyor.")

    def _export_to_excel(self):
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

        ExcelService.export_excel(
            self,
            headers,
            rows,
            "Cari_Hareket_Kayitlari.xlsx",
            sheet_title="Cari Hareket Kayıtları",
            success_message="Excel dosyası başarıyla export edildi.",
        )

    def _export_to_pdf(self):
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

        PDFService.generate_pdf(
            self,
            headers,
            rows,
            "Cari_Hareket_Kayitlari.pdf",
            "Cari Hareket Kayıtları",
        )

    def _print_table(self):
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

        PrintService.print_report(self, headers, rows, "Cari Hareket Kayıtları")

    def _open_whatsapp_with_statement(self):
        if not self.customer_input.text().strip() or self.selected_supplier_id <= 0:
            QMessageBox.warning(self, "Uyarı", "Lütfen önce bir müşteri seçin.")
            return

        phone = self._selected_customer_phone()
        normalized_phone = self._normalize_phone_for_whatsapp(phone)
        if not normalized_phone:
            QMessageBox.warning(self, "Uyarı", "This customer does not have a WhatsApp number.")
            return

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

        self._cleanup_temp_pdfs()
        try:
            temp_file = tempfile.NamedTemporaryFile(prefix="mewa_cari_ekstre_", suffix=".pdf", delete=False)
            temp_pdf_path = temp_file.name
            temp_file.close()
        except Exception as exc:
            QMessageBox.critical(self, "Hata", f"PDF dosyası hazırlanamadı:\n{exc}")
            return

        ok, error_message = PDFService.generate_pdf_to_path(
            headers=headers,
            rows=rows,
            save_path=temp_pdf_path,
            title="Cari Hareket Kayıtları",
        )
        if not ok:
            try:
                if os.path.exists(temp_pdf_path):
                    os.remove(temp_pdf_path)
            except OSError:
                pass
            QMessageBox.critical(self, "Hata", f"PDF oluşturulurken bir hata oluştu:\n{error_message}")
            return

        self._temp_pdf_files.add(temp_pdf_path)

        default_message = (
            "Hello,\n\n"
            "Please find attached your current account statement.\n\n"
            "Best regards,\n"
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
            QMessageBox.warning(self, "Uyarı", "WhatsApp açılamadı.")
            return

        QMessageBox.information(
            self,
            "Bilgi",
            "WhatsApp konuşması hazırlandı. PDF eklentisi için dosya yolu hazır:\n"
            f"{temp_pdf_path}\n\n"
            "Mesajı kontrol edip Gönder'e basın.",
        )

    def _selected_customer_phone(self) -> str:
        if self.selected_cari is not None:
            phone = str(self.selected_cari.get("telefon") or self.selected_cari.get("phone") or "").strip()
            if phone:
                return phone

        cari_kodu = self.customer_code_input.text().strip()
        if cari_kodu:
            phone = CariModel.telefon_bilgisi(cari_kodu)
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
        FinanceModel.unregister_listener(self._listener)
        self._cleanup_temp_pdfs()
        super().closeEvent(event)
