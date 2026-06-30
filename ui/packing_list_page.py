import tempfile
from urllib.parse import quote

from PySide6.QtCore import QSettings, Qt, QUrl
from PySide6.QtGui import QAction, QDesktopServices, QKeySequence, QShortcut
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

from models.packing_list_model import PackingListModel
from services.document_preview_engine import (
    DocumentLineItem,
    DocumentPreviewWindow,
    DocumentTemplate,
    ExcelExporter,
    PDFExporter,
    PrintManager,
)
from services.proforma_conversion_service import ProformaConversionService
from services.whatsapp_service import WhatsAppService
from shared.widgets.list_context_menu import ListContextMenuAction, ListContextMenuBuilder
from shared.widgets.table_column_state import add_layout_lock_toggle, apply_table_column_standard
from shared.widgets.table_visual import apply_list_table_visuals, create_record_count_label, set_record_count
from ui.new_packing_list_dialog import NewPackingListDialog
from ui.packing_list_source_dialog import PackingListSourceDialog


class PackingListPage(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Çeki Listesi / Packing List")
        self.resize(1360, 760)

        self.settings = QSettings("MeWa", "ERP")
        self._rows = []
        self._current_preview_window = None
        self._context_menu_builder = ListContextMenuBuilder(self)
        self._setup_ui()
        self._setup_shortcuts()
        self.load_packing_lists()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title = QLabel("📦 Çeki Listesi / Packing List")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size:24px; font-weight:bold; padding:8px 0;")
        layout.addWidget(title)

        search_label = QLabel("Search")
        layout.addWidget(search_label)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Packing List No, Customer, Invoice, Proforma")
        self.search_input.textChanged.connect(self.load_packing_lists)
        layout.addWidget(self.search_input)

        self.toolbar = QToolBar()
        self.toolbar.setMovable(False)
        layout.addWidget(self.toolbar)

        self.action_new = QAction("New", self)
        self.action_delete = QAction("🗑 Delete", self)
        self.action_excel = QAction("Excel", self)
        self.action_pdf = QAction("PDF", self)
        self.action_print = QAction("Print", self)
        self.action_whatsapp = QAction("WhatsApp", self)
        self.action_email = QAction("Email", self)
        self.action_website = QAction("Website", self)
        self.action_columns = QAction("Column Visibility", self)

        for action in [
            self.action_new,
            self.action_delete,
            self.action_excel,
            self.action_pdf,
            self.action_print,
            self.action_whatsapp,
            self.action_email,
            self.action_website,
            self.action_columns,
        ]:
            self.toolbar.addAction(action)

        self.action_new.triggered.connect(self._new_packing_list)
        self.action_delete.triggered.connect(self._delete_selected)
        self.action_excel.triggered.connect(self._export_selected_excel)
        self.action_pdf.triggered.connect(self._export_selected_pdf)
        self.action_print.triggered.connect(self._print_selected)
        self.action_whatsapp.triggered.connect(self._whatsapp_selected)
        self.action_email.triggered.connect(self._email_selected)
        self.action_website.triggered.connect(self._website_selected)
        self.action_columns.triggered.connect(self._show_column_menu)

        self.table = QTableWidget()
        self.column_labels = [
            "Packing List No",
            "Date",
            "Customer",
            "Customer Code",
            "Invoice No",
            "Proforma No",
            "Source",
            "Currency",
            "Total Pallets",
            "Total Products",
            "Total Qty",
            "Net Weight",
            "Gross Weight",
            "Status",
            "Created By",
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
        self.table.doubleClicked.connect(self._open_selected)
        apply_list_table_visuals(self.table)

        apply_table_column_standard(self.table, self.settings, "packing_list_table", keep_last_column_stretch=False)
        self.action_layout_lock = add_layout_lock_toggle(
            self.toolbar,
            self.table,
            self.settings,
            "packing_list_table",
            self,
            keep_last_column_stretch=False,
        )
        self.action_layout_lock.setText("Lock Layout")
        self.action_layout_lock.toggled.connect(
            lambda checked: self.action_layout_lock.setText("Unlock Layout" if checked else "Lock Layout")
        )

        layout.addWidget(self.table)

        stats = QFrame()
        stats.setStyleSheet("QFrame{background:#0f172a; border:1px solid #334155; border-radius:12px;}")
        stats_layout = QGridLayout(stats)
        self.stats_cards = []
        for idx, (name, icon) in enumerate([
            ("Total Packing Lists", "📦"),
            ("Total Pallets", "🧱"),
            ("Total Qty", "#"),
            ("Total Gross Weight", "⚖"),
        ]):
            card = QFrame()
            card.setStyleSheet("QFrame{background:#111827; border:1px solid #334155; border-radius:12px;}")
            card_layout = QVBoxLayout(card)
            value = QLabel("0")
            value.setStyleSheet("font-size:22px; font-weight:bold; color:#f8fafc;")
            label = QLabel(f"{icon} {name}")
            label.setStyleSheet("font-size:12px; color:#94a3b8;")
            card_layout.addWidget(value)
            card_layout.addWidget(label)
            stats_layout.addWidget(card, 0, idx)
            self.stats_cards.append(value)
        layout.addWidget(stats)

        footer = QHBoxLayout()
        footer.addStretch()
        self.record_count_label = create_record_count_label()
        footer.addWidget(self.record_count_label)
        layout.addLayout(footer)

        self.setStyleSheet(
            self.styleSheet()
            + "QLabel{color:#e2e8f0;} QLineEdit{background:#0f172a; color:#e2e8f0; border:1px solid #334155; border-radius:8px; padding:8px;}"
        )

    def _setup_shortcuts(self):
        shortcut_open = QShortcut(QKeySequence(Qt.Key_Return), self)
        shortcut_open.activated.connect(self._open_selected)
        shortcut_delete = QShortcut(QKeySequence(Qt.Key_Delete), self)
        shortcut_delete.activated.connect(self._delete_selected)
        shortcut_preview = QShortcut(QKeySequence("Ctrl+P"), self)
        shortcut_preview.activated.connect(self._preview_selected)
        shortcut_print = QShortcut(QKeySequence("Ctrl+Shift+P"), self)
        shortcut_print.activated.connect(self._print_selected)

    def _selected_number(self) -> str:
        row = self.table.currentRow()
        if row < 0:
            return ""
        item = self.table.item(row, 0)
        return "" if item is None else item.text().strip()

    def _selected_detail(self):
        number = self._selected_number()
        if not number:
            return None
        return PackingListModel.packing_list_detail(number)

    def _selected_row_data(self) -> Optional[dict]:
        number = self._selected_number()
        if not number:
            return None
        for row in self._rows:
            if str(row.get("packing_list_number") or "") == number:
                return row
        return None

    def _detail_to_template(self, detail: dict) -> DocumentTemplate:
        items = []
        for item in detail.get("items", []):
            desc = (
                f"{item.get('description', '')} | "
                f"Pallet: {item.get('pallet_no', '')} | "
                f"HS: {item.get('hs_code', '')} | "
                f"Net: {float(item.get('net_weight') or 0):.3f} | "
                f"Gross: {float(item.get('gross_weight') or 0):.3f} | "
                f"{item.get('remarks', '')}"
            ).strip(" |")
            items.append(
                DocumentLineItem(
                    line_no=len(items) + 1,
                    product_code=str(item.get("stock_code") or ""),
                    description=desc,
                    quantity=f"{float(item.get('quantity') or 0):.3f}",
                    unit=str(item.get("unit") or ""),
                    unit_price="",
                    discount="",
                    vat="",
                    total=f"{float(item.get('gross_weight') or 0):.3f}",
                    amount=f"{float(item.get('net_weight') or 0):.3f}",
                )
            )

        terms = (
            f"Invoice No: {detail.get('invoice_number', '')}\n"
            f"Proforma No: {detail.get('proforma_number', '')}\n"
            f"Container No: {detail.get('container_no', '')}\n"
            f"Seal No: {detail.get('seal_no', '')}\n"
            f"Port of Loading: {detail.get('port_of_loading', '')}\n"
            f"Port of Discharge: {detail.get('port_of_discharge', '')}"
        )

        return DocumentTemplate(
            document_title="PACKING LIST",
            filename_base=str(detail.get("packing_list_number") or "packing_list").replace("/", "-"),
            document_kind="PACKING_LIST",
            invoice_number=str(detail.get("packing_list_number") or ""),
            invoice_date=str(detail.get("packing_date") or ""),
            currency=str(detail.get("currency") or "USD"),
            customer_name=str(detail.get("customer_name") or ""),
            customer_company_name=str(detail.get("customer_name") or ""),
            customer_country=str(detail.get("country") or ""),
            customer_code=str(detail.get("customer_code") or ""),
            bill_to_company=str(detail.get("consignee") or ""),
            ship_to_company=str(detail.get("notify_party") or ""),
            payment_terms=str(detail.get("payment_terms") or ""),
            delivery_terms=str(detail.get("delivery_terms") or ""),
            estimated_delivery=str(detail.get("estimated_delivery") or ""),
            packing_type=str(detail.get("container_no") or ""),
            subtotal=f"{float(detail.get('total_net_weight') or 0):.3f}",
            net_total=f"{float(detail.get('total_net_weight') or 0):.3f}",
            grand_total=f"{float(detail.get('total_gross_weight') or 0):.3f}",
            notes=str(detail.get("notes") or ""),
            terms_conditions=terms,
            items=items,
        )

    def load_packing_lists(self, keyword: str = ""):
        rows = PackingListModel.list_packing_lists(keyword)
        self._rows = rows

        sorting = self.table.isSortingEnabled()
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(rows))

        for r, row in enumerate(rows):
            values = [
                row.get("packing_list_number", ""),
                row.get("packing_date", ""),
                row.get("customer_name", ""),
                row.get("customer_code", ""),
                row.get("invoice_number", ""),
                row.get("proforma_number", ""),
                f"{row.get('source_type', '')}:{row.get('source_number', '')}",
                row.get("currency", "USD"),
                str(int(row.get("total_pallets") or 0)),
                str(int(row.get("total_products") or 0)),
                f"{float(row.get('total_quantity') or 0):.3f}",
                f"{float(row.get('total_net_weight') or 0):.3f}",
                f"{float(row.get('total_gross_weight') or 0):.3f}",
                row.get("status", "Draft"),
                row.get("created_by", "SYSTEM"),
            ]
            for c, val in enumerate(values):
                self.table.setItem(r, c, QTableWidgetItem(str(val)))

        self.table.setSortingEnabled(sorting)
        set_record_count(self.record_count_label, len(rows))
        self._update_stats(rows)

    def _update_stats(self, rows):
        total_lists = len(rows)
        total_pallets = sum(int(row.get("total_pallets") or 0) for row in rows)
        total_qty = sum(float(row.get("total_quantity") or 0) for row in rows)
        total_gross = sum(float(row.get("total_gross_weight") or 0) for row in rows)

        self.stats_cards[0].setText(str(total_lists))
        self.stats_cards[1].setText(str(total_pallets))
        self.stats_cards[2].setText(f"{total_qty:.3f}")
        self.stats_cards[3].setText(f"{total_gross:.3f}")

    def _new_packing_list(self):
        selected = PackingListSourceDialog.select_source(self)
        if selected is None:
            return
        dialog = NewPackingListDialog(
            source_type=str(selected.get("source_type") or ""),
            source_number=str(selected.get("source_number") or ""),
            parent=self,
        )
        if dialog.exec():
            self.load_packing_lists(self.search_input.text())

    def _open_selected(self):
        number = self._selected_number()
        if not number:
            return
        dialog = NewPackingListDialog(packing_list_number=number, parent=self)
        if dialog.exec():
            self.load_packing_lists(self.search_input.text())

    def _duplicate_selected(self):
        number = self._selected_number()
        if not number:
            QMessageBox.warning(self, "Warning", "Select a Packing List first.")
            return
        dialog = NewPackingListDialog(parent=self)
        dialog.load_duplicate_data(number)
        if dialog.exec():
            self.load_packing_lists(self.search_input.text())

    def _convert_selected_to_export_invoice(self):
        row = self._selected_row_data()
        if row is None:
            QMessageBox.warning(self, "Warning", "Select a Packing List first.")
            return
        source_type = str(row.get("source_type") or "")
        source_number = str(row.get("source_number") or "")
        if source_type != "Proforma" or not source_number:
            QMessageBox.warning(self, "Warning", "Only Packing Lists created from Proforma can be converted.")
            return
        created_by = os.getenv("USERNAME") or os.getenv("USER") or "SYSTEM"
        try:
            result = ProformaConversionService.convert_to_export_sales_invoice(source_number, created_by=created_by)
            QMessageBox.information(
                self,
                "Success",
                f"Export Sales Invoice created: {result.get('sales_invoice_number', '')}",
            )
        except Exception as exc:
            QMessageBox.warning(self, "Warning", str(exc))

    def _delete_selected(self):
        detail = self._selected_detail()
        if detail is None:
            QMessageBox.warning(self, "Warning", "Select a Packing List first.")
            return

        answer = QMessageBox.question(
            self,
            "Delete Packing List",
            (
                "Packing List No:\n\n"
                f"{detail.get('packing_list_number', '')}\n\n"
                "Customer:\n\n"
                f"{detail.get('customer_name', '')}\n\n"
                "Are you sure you want to permanently delete this Packing List?"
            ),
            QMessageBox.Yes | QMessageBox.Cancel,
            QMessageBox.Cancel,
        )
        if answer != QMessageBox.Yes:
            return

        try:
            deleted = PackingListModel.delete_packing_list(str(detail.get("packing_list_number") or ""))
            if not deleted:
                QMessageBox.warning(self, "Warning", "Packing List could not be deleted.")
                return
            self.load_packing_lists(self.search_input.text())
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Delete failed:\n{exc}")

    def _preview_selected(self):
        detail = self._selected_detail()
        if detail is None:
            QMessageBox.warning(self, "Warning", "Select a Packing List first.")
            return
        template = self._detail_to_template(detail)
        self._current_preview_window = DocumentPreviewWindow(template=template, parent=self)
        self._current_preview_window.show()
        self._current_preview_window.raise_()
        self._current_preview_window.activateWindow()

    def _print_selected(self):
        detail = self._selected_detail()
        if detail is None:
            QMessageBox.warning(self, "Warning", "Select a Packing List first.")
            return
        template = self._detail_to_template(detail)
        PrintManager.print_template(self, template, rotation=0)

    def _export_selected_pdf(self):
        detail = self._selected_detail()
        if detail is None:
            QMessageBox.warning(self, "Warning", "Select a Packing List first.")
            return
        template = self._detail_to_template(detail)
        from PySide6.QtWidgets import QFileDialog

        path, _ = QFileDialog.getSaveFileName(self, "Save PDF", f"{template.filename_base}.pdf", "PDF Files (*.pdf)")
        if not path:
            return
        ok, err = PDFExporter.export_to_path(template, path)
        if not ok:
            QMessageBox.critical(self, "Error", f"PDF export failed:\n{err}")
            return
        QMessageBox.information(self, "Success", "PDF exported successfully.")

    def _export_selected_excel(self):
        detail = self._selected_detail()
        if detail is None:
            QMessageBox.warning(self, "Warning", "Select a Packing List first.")
            return
        template = self._detail_to_template(detail)
        from PySide6.QtWidgets import QFileDialog

        path, _ = QFileDialog.getSaveFileName(self, "Save Excel", f"{template.filename_base}.xlsx", "Excel Files (*.xlsx)")
        if not path:
            return
        if not path.lower().endswith(".xlsx"):
            path = f"{path}.xlsx"
        if not ExcelExporter.export_to_path(template, path):
            QMessageBox.critical(self, "Error", "Excel export failed.")
            return
        QMessageBox.information(self, "Success", "Excel exported successfully.")

    def _whatsapp_selected(self):
        detail = self._selected_detail()
        if detail is None:
            QMessageBox.warning(self, "Warning", "Select a Packing List first.")
            return

        template = self._detail_to_template(detail)

        def ensure_pdf() -> str:
            tmp = tempfile.NamedTemporaryFile(prefix="mewa_packing_", suffix=".pdf", delete=False)
            tmp.close()
            ok, err = PDFExporter.export_to_path(template, tmp.name)
            if not ok:
                QMessageBox.critical(self, "Error", f"Could not prepare PDF:\n{err}")
                return ""
            return tmp.name

        message = (
            "Hello,\n\n"
            "Please find attached your Packing List.\n\n"
            "Packing List No:\n"
            f"{template.invoice_number}\n\n"
            "Best Regards\n\n"
            "MeWa Automotive Ltd.Şti."
        )
        WhatsAppService.send_document(
            parent=self,
            customer_code=template.customer_code,
            customer_name=template.customer_name,
            preferred_whatsapp=template.customer_whatsapp,
            message=message,
            ensure_pdf_path=ensure_pdf,
        )

    def _email_selected(self):
        detail = self._selected_detail()
        if detail is None:
            QMessageBox.warning(self, "Warning", "Select a Packing List first.")
            return

        template = self._detail_to_template(detail)
        tmp = tempfile.NamedTemporaryFile(prefix="mewa_packing_", suffix=".pdf", delete=False)
        tmp.close()
        ok, err = PDFExporter.export_to_path(template, tmp.name)
        if not ok:
            QMessageBox.critical(self, "Error", f"Could not prepare PDF:\n{err}")
            return

        subject = quote(f"Packing List - {template.invoice_number}")
        body = quote(f"Dear Customer,\n\nPlease find your Packing List attached.\n\nFile: {tmp.name}")
        opened = QDesktopServices.openUrl(QUrl(f"mailto:?subject={subject}&body={body}"))
        if not opened:
            QMessageBox.warning(self, "Warning", f"Could not open mail client. PDF ready:\n{tmp.name}")

    def _website_selected(self):
        opened = QDesktopServices.openUrl(QUrl("https://mewaautomotive.com"))
        if not opened:
            QMessageBox.warning(self, "Warning", "Website could not be opened.")

    def _show_column_menu(self):
        menu = QMenu(self)
        for i, label in enumerate(self.column_labels):
            action = QAction(label, self)
            action.setCheckable(True)
            action.setChecked(not self.table.isColumnHidden(i))
            action.triggered.connect(lambda checked, col=i: self.table.setColumnHidden(col, not checked))
            menu.addAction(action)
        menu.exec_(self.toolbar.mapToGlobal(self.toolbar.rect().bottomLeft()))

    def _show_context_menu(self, pos):
        row = self.table.rowAt(pos.y())
        if row >= 0:
            self.table.selectRow(row)

        row_data = self._selected_row_data() or {}
        can_convert = str(row_data.get("source_type") or "") == "Proforma"
        menu = self._context_menu_builder.build(
            [
                ListContextMenuAction("📂 Open", self._open_selected),
                ListContextMenuAction("👁 Preview", self._preview_selected),
                ListContextMenuAction("🖨 Print", self._print_selected),
                ListContextMenuAction("📄 Save PDF", self._export_selected_pdf),
                ListContextMenuAction("📊 Export Excel", self._export_selected_excel),
                ListContextMenuAction("📑 Duplicate", self._duplicate_selected),
                ListContextMenuAction("🧾 Convert to Export Invoice", self._convert_selected_to_export_invoice, enabled=can_convert),
                ListContextMenuAction("🗑 Delete", self._delete_selected, separator_before=True),
            ]
        )
        menu.exec_(self.table.viewport().mapToGlobal(pos))
