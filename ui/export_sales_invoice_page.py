from pathlib import Path
import traceback

from PySide6.QtCore import Qt, QSettings
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
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

from models.export_sales_invoice_model import ExportSalesInvoiceModel
from shared.widgets.base_document_toolbar import BaseDocumentToolbar
from shared.widgets.table_column_state import apply_table_column_standard
from shared.widgets.table_visual import apply_list_table_visuals, create_record_count_label, set_record_count
from ui.base_document_page import BaseDocumentPage
from ui.new_export_sales_invoice_dialog import NewExportSalesInvoiceDialog
from ui.new_packing_list_dialog import NewPackingListDialog


class ExportSalesInvoicePage(BaseDocumentPage):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Yurtdışı Satış Faturaları")
        self.resize(1280, 720)
        self._logo_path = self._resolve_logo_path()
        self._rows = []
        self._setup_ui()
        self.load_invoices()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        self.page_title = QLabel("🧾 Yurtdışı Satış Faturaları")
        self.page_title.setAlignment(Qt.AlignCenter)
        self.page_title.setStyleSheet("font-size:24px; font-weight:bold; padding:8px 0;")
        layout.addWidget(self.page_title)

        search_label = QLabel("Ara:")
        search_label.setStyleSheet("font-weight:bold;")
        layout.addWidget(search_label)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Fatura No, Müşteri veya Durum")
        self.search_input.textChanged.connect(self._handle_search)
        layout.addWidget(self.search_input)

        self.toolbar = QToolBar()
        self.toolbar.setMovable(False)
        layout.addWidget(self.toolbar)

        self.action_new = QAction("➕ Yeni Yurtdışı Satış Faturası", self)
        self.action_new.triggered.connect(self._new_invoice)
        self.toolbar.addAction(self.action_new)

        self.action_edit = QAction("✏️ Düzenle", self)
        self.action_edit.triggered.connect(self._edit_selected)
        self.toolbar.addAction(self.action_edit)

        self.action_cancel = QAction("🛑 İptal", self)
        self.action_cancel.triggered.connect(self._cancel_selected)
        self.toolbar.addAction(self.action_cancel)

        self.action_create_packing_list = QAction("📦 Çeki Listesi Oluştur", self)
        self.action_create_packing_list.triggered.connect(self._create_packing_list_from_selected)
        self.toolbar.addAction(self.action_create_packing_list)

        self.toolbar.addSeparator()

        self.toolbar.addSeparator()

        self.stats_layout = QGridLayout()
        self.stats_layout.setSpacing(12)
        self.stats_container = QFrame()
        self.stats_container.setStyleSheet(
            "QFrame{background-color:#0f172a; border:1px solid #334155; border-radius:12px;}"
        )
        self.stats_container.setLayout(self.stats_layout)
        layout.addWidget(self.stats_container)

        self.stats_cards = []
        for title, icon in [
            ("Toplam Fatura", "🧾"),
            ("İşlenmiş Fatura", "✅"),
            ("İptal Fatura", "🛑"),
            ("Toplam Tutar", "💰"),
        ]:
            card = QFrame()
            card.setStyleSheet(
                "QFrame{background-color:#111827; border:1px solid #334155; border-radius:12px;}"
            )
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(14, 14, 14, 14)
            card_layout.setSpacing(6)

            value = QLabel("0")
            value.setObjectName("statValue")
            value.setStyleSheet("font-size:22px; font-weight:bold; color:#f8fafc;")
            label = QLabel(f"{icon} {title}")
            label.setStyleSheet("font-size:12px; color:#94a3b8;")

            card_layout.addWidget(value)
            card_layout.addWidget(label)
            self.stats_layout.addWidget(card, 0, len(self.stats_cards))
            self.stats_cards.append((title, value))

        self.table = QTableWidget()
        self.table.setObjectName("exportSalesInvoiceTable")
        self.column_labels = [
            "Fatura No",
            "Fatura Tarihi",
            "Müşteri",
            "Cari Kod",
            "Para Birimi",
            "Genel Toplam",
            "Durum",
            "Oluşturan",
        ]
        self.table.setColumnCount(len(self.column_labels))
        self.table.setHorizontalHeaderLabels(self.column_labels)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSortingEnabled(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        self.table.doubleClicked.connect(self._edit_selected)
        apply_list_table_visuals(self.table)

        self.settings = QSettings("MeWa", "ERP")
        self._restore_column_visibility()
        apply_table_column_standard(
            self.table,
            self.settings,
            "export_sales_invoice_table",
            keep_last_column_stretch=False,
        )
        self.document_toolbar = BaseDocumentToolbar(
            parent=self,
            toolbar=self.toolbar,
            table=self.table,
            settings=self.settings,
            layout_key="export_sales_invoice_table",
            payload_provider=self._document_payload,
        )

        layout.addWidget(self.table)

        footer = QHBoxLayout()
        footer.addStretch()
        self.record_count_label = create_record_count_label()
        footer.addWidget(self.record_count_label)
        layout.addLayout(footer)

        self.setStyleSheet(
            self.styleSheet()
            + "QLabel{color:#e2e8f0;} QLineEdit{background:#0f172a; color:#e2e8f0; border:1px solid #334155; border-radius:8px; padding:8px;}"
        )

    def _handle_search(self, text: str):
        self.load_invoices(text)

    def load_invoices(self, keyword: str = ""):
        rows = ExportSalesInvoiceModel.list_invoices(keyword)
        self._rows = rows

        sorting = self.table.isSortingEnabled()
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(rows))

        for row_index, row in enumerate(rows):
            values = [
                row.get("invoice_number", ""),
                row.get("invoice_date", ""),
                row.get("customer_name", ""),
                row.get("customer_code", ""),
                row.get("currency", "USD"),
                f"{float(row.get('grand_total') or 0):.2f}",
                self._status_text(row.get("status", "")),
                row.get("created_by", "SYSTEM"),
            ]
            for col, value in enumerate(values):
                self.table.setItem(row_index, col, QTableWidgetItem("" if value is None else str(value)))

        self.table.setSortingEnabled(sorting)
        set_record_count(self.record_count_label, len(rows))
        self._update_stats(rows)

    def _update_stats(self, rows):
        total = len(rows)
        posted = sum(1 for row in rows if str(row.get("status") or "").lower() == "posted")
        cancelled = sum(1 for row in rows if str(row.get("status") or "").lower() == "cancelled")
        amount = sum(float(row.get("grand_total") or 0) for row in rows)

        self.stats_cards[0][1].setText(str(total))
        self.stats_cards[1][1].setText(str(posted))
        self.stats_cards[2][1].setText(str(cancelled))
        self.stats_cards[3][1].setText(f"{amount:,.2f} USD")

    def _new_invoice(self):
        try:
            dialog = NewExportSalesInvoiceDialog(parent=self)
            if dialog.exec():
                self.load_invoices(self.search_input.text())
        except Exception as exc:
            traceback.print_exc()
            QMessageBox.critical(self, "Hata", f"Yeni Yurtdışı Satış Faturası penceresi açılamadı:\n{exc}")

    def _edit_selected(self):
        invoice_no = self._selected_invoice_no()
        if not invoice_no:
            return
        try:
            dialog = NewExportSalesInvoiceDialog(invoice_number=invoice_no, parent=self)
            if dialog.exec():
                self.load_invoices(self.search_input.text())
        except Exception as exc:
            traceback.print_exc()
            QMessageBox.critical(self, "Hata", f"Yurtdışı Satış Faturası düzenleme penceresi açılamadı:\n{exc}")

    def _cancel_selected(self):
        invoice_no = self._selected_invoice_no()
        if not invoice_no:
            return

        answer = QMessageBox.question(
            self,
            "Yurtdışı Satış Faturasını İptal Et",
            "Bu işlem faturayı iptal durumuna alır. Devam edilsin mi?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return

        try:
            ExportSalesInvoiceModel.cancel_invoice(invoice_no)
            self.load_invoices(self.search_input.text())
        except Exception as exc:
            QMessageBox.critical(self, "Hata", f"Yurtdışı satış faturası iptal işlemi başarısız oldu:\n{exc}")

    def _show_column_menu(self):
        menu = QMenu(self)
        for index, label in enumerate(self.column_labels):
            action = QAction(label, self)
            action.setCheckable(True)
            action.setChecked(not self.table.isColumnHidden(index))
            action.triggered.connect(lambda checked, col=index: self._set_column_visibility(col, checked))
            menu.addAction(action)
        menu.exec_(self.toolbar.mapToGlobal(self.toolbar.rect().bottomLeft()))

    def _show_context_menu(self, pos):
        row = self.table.rowAt(pos.y())
        if row >= 0:
            self.table.selectRow(row)

        menu = QMenu(self)
        edit_action = QAction("Düzenle", self)
        edit_action.triggered.connect(self._edit_selected)
        cancel_action = QAction("İptal", self)
        cancel_action.triggered.connect(self._cancel_selected)
        packing_action = QAction("Çeki Listesi Oluştur", self)
        packing_action.triggered.connect(self._create_packing_list_from_selected)
        menu.addAction(edit_action)
        menu.addAction(cancel_action)
        menu.addSeparator()
        menu.addAction(packing_action)
        menu.exec_(self.table.viewport().mapToGlobal(pos))

    def _create_packing_list_from_selected(self):
        invoice_no = self._selected_invoice_no()
        if not invoice_no:
            QMessageBox.warning(self, "Uyarı", "Önce bir fatura seçin.")
            return

        dialog = NewPackingListDialog(source_type="SalesInvoice", source_number=invoice_no, parent=self)
        if dialog.exec():
            QMessageBox.information(self, "Başarılı", "Çeki listesi oluşturuldu.")

    def _selected_invoice_no(self):
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        if item is None:
            return None
        value = item.text().strip()
        return value or None

    def _set_column_visibility(self, index: int, visible: bool):
        self.table.setColumnHidden(index, not visible)
        self.settings.setValue(f"export_sales_invoice_columns/{index}", visible)

    def _document_payload(self):
        headers = self.column_labels
        rows = []
        for row in range(self.table.rowCount()):
            values = []
            for col in range(self.table.columnCount()):
                item = self.table.item(row, col)
                values.append("" if item is None else item.text())
            rows.append(values)

        selected_row = self.table.currentRow()
        customer_name = ""
        customer_code = ""
        document_no = self._selected_invoice_no() or ""
        if selected_row >= 0:
            c_item = self.table.item(selected_row, 2)
            cc_item = self.table.item(selected_row, 3)
            customer_name = "" if c_item is None else c_item.text()
            customer_code = "" if cc_item is None else cc_item.text()

        return {
            "title": "Export Sales Invoice",
            "filename_base": "export_sales_invoice",
            "headers": headers,
            "rows": rows,
            "document_number": document_no,
            "currency": "USD",
            "customer_name": customer_name,
            "customer_code": customer_code,
            "totals": {"Grand Total": self.stats_cards[3][1].text()},
        }

    def _restore_column_visibility(self):
        for index, _ in enumerate(self.column_labels):
            visible = self.settings.value(f"export_sales_invoice_columns/{index}", True)
            self.table.setColumnHidden(index, not visible)

    def _export_to_excel(self):
        headers = self.column_labels
        rows = []
        for row in range(self.table.rowCount()):
            values = []
            for col in range(self.table.columnCount()):
                item = self.table.item(row, col)
                values.append("" if item is None else item.text())
            rows.append(values)

        ExcelService.export_excel(
            self,
            headers,
            rows,
            "Yurtdisi_Satis_Fatura_Listesi.xlsx",
            sheet_title="Yurtdışı Satış Faturaları",
            success_message="Excel dosyası başarıyla export edildi.",
        )

    def _export_to_pdf(self):
        headers = self.column_labels
        rows = []
        for row in range(self.table.rowCount()):
            values = []
            for col in range(self.table.columnCount()):
                item = self.table.item(row, col)
                values.append("" if item is None else item.text())
            rows.append(values)

        PDFService.generate_pdf(
            self,
            headers,
            rows,
            "Yurtdisi_Satis_Fatura_Listesi.pdf",
            "Yurtdışı Satış Fatura Listesi",
            logo_path=str(self._logo_path) if self._logo_path.exists() else None,
        )

    def _print_table(self):
        headers = self.column_labels
        rows = []
        for row in range(self.table.rowCount()):
            values = []
            for col in range(self.table.columnCount()):
                item = self.table.item(row, col)
                values.append("" if item is None else item.text())
            rows.append(values)

        PrintService.print_report(self, headers, rows, "Yurtdışı Satış Fatura Listesi")

    def _resolve_logo_path(self) -> Path:
        project_root = Path(__file__).resolve().parent.parent
        official = project_root / "assets" / "logos" / "mewa_logo.png"
        fallback = project_root / "assets" / "logo.png"
        return official if official.exists() else fallback

    @staticmethod
    def _status_text(status: str) -> str:
        mapping = {
            "draft": "Taslak",
            "approved": "Onaylı",
            "cancelled": "İptal",
            "posted": "İşlenmiş",
        }
        return mapping.get(str(status or "").strip().lower(), str(status or ""))
