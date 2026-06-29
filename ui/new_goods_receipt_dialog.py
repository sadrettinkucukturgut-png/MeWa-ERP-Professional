import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QFormLayout,
    QGridLayout,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from models.goods_receipt_model import GoodsReceiptModel
from services.document_preview_engine import (
    DocumentLineItem,
    DocumentPreviewController,
    DocumentTemplate,
    build_template_signature,
    resolve_party_details,
)


class NewGoodsReceiptDialog(QDialog):
    COL_STOCK_CODE = 0
    COL_BARCODE = 1
    COL_PRODUCT_NAME = 2
    COL_ORDERED = 3
    COL_RECEIVED = 4
    COL_REMAINING = 5
    COL_UNIT = 6
    COL_WAREHOUSE = 7

    def __init__(self, receipt_number: Optional[str] = None, parent=None):
        super().__init__(parent)
        self.receipt_number = receipt_number
        self.is_edit_mode = bool(receipt_number)
        self.saved_receipt_number = ""
        self._purchase_orders: List[Dict[str, Any]] = []
        self._preview_controller: Optional[DocumentPreviewController] = None
        self._has_persisted_document = self.is_edit_mode
        self._last_saved_signature = ""

        self.setWindowTitle("Mal Kabul Düzenle" if self.is_edit_mode else "Yeni Mal Kabul")
        self.resize(1100, 820)

        self._setup_ui()
        self._load_purchase_order_lookup()

        if self.is_edit_mode and receipt_number:
            self._load_receipt(receipt_number)
        else:
            self.receipt_number_input.setText(GoodsReceiptModel.receipt_number_generate())
            self.receipt_date_input.setDate(QDate.currentDate())

        self._initialize_preview_state()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFrameShape(QScrollArea.NoFrame)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(20, 20, 20, 20)
        content_layout.setSpacing(14)

        title = QLabel("📦 Mal Kabul")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        content_layout.addWidget(title)

        form_widget = QWidget()
        form_layout = QFormLayout(form_widget)
        form_layout.setLabelAlignment(Qt.AlignLeft)
        form_layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)

        self.receipt_number_input = QLineEdit()
        self.receipt_number_input.setReadOnly(True)

        self.purchase_order_combo = QComboBox()
        self.purchase_order_combo.setEditable(True)
        self.purchase_order_combo.setInsertPolicy(QComboBox.NoInsert)
        self.purchase_order_combo.currentTextChanged.connect(self._on_purchase_order_changed)

        self.supplier_input = QLineEdit()
        self.supplier_input.setReadOnly(True)

        self.warehouse_input = QLineEdit()
        self.receipt_date_input = QDateEdit()
        self.receipt_date_input.setCalendarPopup(True)
        self.notes_input = QTextEdit()
        self.notes_input.setFixedHeight(84)

        form_layout.addRow("Fiş Numarası", self.receipt_number_input)
        form_layout.addRow("Satın Alma Siparişi", self.purchase_order_combo)
        form_layout.addRow("Tedarikçi", self.supplier_input)
        form_layout.addRow("Depo", self.warehouse_input)
        form_layout.addRow("Fiş Tarihi", self.receipt_date_input)
        form_layout.addRow("Notlar", self.notes_input)

        content_layout.addWidget(form_widget)

        self.product_table = QTableWidget()
        self.product_table.setColumnCount(8)
        self.product_table.setHorizontalHeaderLabels(
            [
                "Stok Kodu",
                "Barkod",
                "Ürün Adı",
                "Sipariş Miktarı",
                "Teslim Alınan",
                "Kalan Miktar",
                "Birim",
                "Depo",
            ]
        )
        self.product_table.setAlternatingRowColors(True)
        self.product_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.product_table.setSelectionMode(QTableWidget.SingleSelection)
        self.product_table.setSortingEnabled(False)
        self.product_table.verticalHeader().setVisible(False)
        self.product_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.product_table.horizontalHeader().setStretchLastSection(False)
        self.product_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.product_table.itemChanged.connect(self._on_item_changed)
        content_layout.addWidget(self.product_table)

        totals_frame = QWidget()
        totals_layout = QGridLayout(totals_frame)
        totals_layout.setContentsMargins(0, 0, 0, 0)
        totals_layout.setHorizontalSpacing(12)

        self.total_ordered_label = QLabel("0.00")
        self.total_received_label = QLabel("0.00")
        self.total_remaining_label = QLabel("0.00")

        totals_layout.addWidget(QLabel("Toplam Sipariş"), 0, 0)
        totals_layout.addWidget(self.total_ordered_label, 0, 1)
        totals_layout.addWidget(QLabel("Toplam Teslim Alınan"), 1, 0)
        totals_layout.addWidget(self.total_received_label, 1, 1)
        totals_layout.addWidget(QLabel("Toplam Kalan"), 2, 0)
        totals_layout.addWidget(self.total_remaining_label, 2, 1)
        content_layout.addWidget(totals_frame)

        button_row = QHBoxLayout()
        button_row.addStretch()
        self.preview_btn = QPushButton("Önizleme")
        self.preview_btn.clicked.connect(self._on_preview)
        self.save_btn = QPushButton("Kaydet")
        self.save_btn.clicked.connect(self._on_save)
        self.save_btn.setDefault(True)
        self.cancel_btn = QPushButton("İptal")
        self.cancel_btn.clicked.connect(self.reject)
        button_row.addWidget(self.preview_btn)
        button_row.addWidget(self.save_btn)
        button_row.addWidget(self.cancel_btn)
        content_layout.addLayout(button_row)

        scroll.setWidget(content)
        layout.addWidget(scroll)

        self.setStyleSheet(
            "QDialog{background:#0b1220;} QLabel{color:#e2e8f0;}"
            "QLineEdit,QComboBox,QDateEdit,QTextEdit{background:#0f172a; color:#e2e8f0; border:1px solid #334155; border-radius:8px; padding:6px;}"
            "QPushButton{background:#1e293b; color:#f8fafc; border:1px solid #334155; border-radius:8px; padding:8px 12px;}"
            "QPushButton:hover{background:#334155;}"
            "QTableWidget{background:#111827; alternate-background-color:#0f172a; color:#e5e7eb; border:1px solid #334155;}"
            "QHeaderView::section{background:#1f2937; color:#e5e7eb; padding:8px 6px;}"
        )

    def _load_purchase_order_lookup(self):
        self._purchase_orders = GoodsReceiptModel.purchase_orders_lookup()
        self.purchase_order_combo.clear()
        self.purchase_order_combo.addItem("")
        for po in self._purchase_orders:
            self.purchase_order_combo.addItem(str(po.get("order_number") or ""))

    def _selected_purchase_order(self) -> Optional[Dict[str, Any]]:
        order_no = self.purchase_order_combo.currentText().strip()
        for po in self._purchase_orders:
            if str(po.get("order_number") or "") == order_no:
                return po
        return None

    def _on_purchase_order_changed(self, _text: str):
        if self.is_edit_mode:
            return
        selected = self._selected_purchase_order()
        if selected is None:
            self.supplier_input.clear()
            self.product_table.setRowCount(0)
            self._update_totals()
            return

        self.supplier_input.setText(str(selected.get("supplier_name") or ""))
        po_id = int(selected.get("id") or 0)
        self._load_purchase_order_products(po_id)

    def _load_purchase_order_products(self, purchase_order_id: int):
        items = GoodsReceiptModel.purchase_order_items_remaining(purchase_order_id)

        self.product_table.blockSignals(True)
        self.product_table.setRowCount(0)
        for item in items:
            row = self.product_table.rowCount()
            self.product_table.insertRow(row)

            stock_code_item = QTableWidgetItem(str(item.get("stock_code") or ""))
            stock_code_item.setFlags(stock_code_item.flags() & ~Qt.ItemIsEditable)
            stock_code_item.setData(Qt.UserRole, int(item.get("stock_id") or 0))
            stock_code_item.setData(Qt.UserRole + 1, int(item.get("purchase_order_item_id") or 0))
            self.product_table.setItem(row, self.COL_STOCK_CODE, stock_code_item)

            barcode_item = QTableWidgetItem(str(item.get("barcode") or ""))
            barcode_item.setFlags(barcode_item.flags() & ~Qt.ItemIsEditable)
            self.product_table.setItem(row, self.COL_BARCODE, barcode_item)

            product_item = QTableWidgetItem(str(item.get("product_name") or ""))
            product_item.setFlags(product_item.flags() & ~Qt.ItemIsEditable)
            self.product_table.setItem(row, self.COL_PRODUCT_NAME, product_item)

            ordered_qty = float(item.get("ordered_qty") or 0)
            remaining_qty = float(item.get("remaining_qty") or 0)

            ordered_item = QTableWidgetItem(f"{ordered_qty:.3f}".rstrip("0").rstrip("."))
            ordered_item.setFlags(ordered_item.flags() & ~Qt.ItemIsEditable)
            self.product_table.setItem(row, self.COL_ORDERED, ordered_item)

            received_item = QTableWidgetItem("0")
            self.product_table.setItem(row, self.COL_RECEIVED, received_item)

            remaining_item = QTableWidgetItem(f"{remaining_qty:.3f}".rstrip("0").rstrip("."))
            remaining_item.setFlags(remaining_item.flags() & ~Qt.ItemIsEditable)
            self.product_table.setItem(row, self.COL_REMAINING, remaining_item)

            unit_item = QTableWidgetItem(str(item.get("unit") or ""))
            unit_item.setFlags(unit_item.flags() & ~Qt.ItemIsEditable)
            self.product_table.setItem(row, self.COL_UNIT, unit_item)

            warehouse_item = QTableWidgetItem(self.warehouse_input.text().strip())
            self.product_table.setItem(row, self.COL_WAREHOUSE, warehouse_item)

        self.product_table.blockSignals(False)
        self._update_totals()

    def _on_item_changed(self, item: QTableWidgetItem):
        if item is None:
            return
        if item.column() == self.COL_RECEIVED:
            row = item.row()
            remaining_item = self.product_table.item(row, self.COL_REMAINING)
            if remaining_item is None:
                return

            max_remaining = self._cell_float(row, self.COL_REMAINING, 0)
            received = self._cell_float(row, self.COL_RECEIVED, 0)
            if received < 0:
                received = 0
            if received > max_remaining:
                received = max_remaining

            self.product_table.blockSignals(True)
            item.setText(f"{received:.3f}".rstrip("0").rstrip("."))
            self.product_table.blockSignals(False)

        self._update_totals()

    def _cell_float(self, row: int, col: int, default: float = 0.0) -> float:
        cell = self.product_table.item(row, col)
        if cell is None:
            return default
        try:
            return float(cell.text().strip() or default)
        except ValueError:
            return default

    def _update_totals(self):
        total_ordered = 0.0
        total_received = 0.0
        total_remaining = 0.0

        for row in range(self.product_table.rowCount()):
            ordered = self._cell_float(row, self.COL_ORDERED, 0)
            received = self._cell_float(row, self.COL_RECEIVED, 0)
            remaining = self._cell_float(row, self.COL_REMAINING, 0)
            total_ordered += ordered
            total_received += received
            total_remaining += remaining

        self.total_ordered_label.setText(f"{total_ordered:,.3f}")
        self.total_received_label.setText(f"{total_received:,.3f}")
        self.total_remaining_label.setText(f"{total_remaining:,.3f}")

    def _load_receipt(self, receipt_number: str):
        detail = GoodsReceiptModel.receipt_detail(receipt_number)
        if detail is None:
            QMessageBox.warning(self, "Uyarı", "Mal kabul kaydı bulunamadı.")
            self.reject()
            return

        self.receipt_number_input.setText(str(detail.get("receipt_number") or ""))
        self.purchase_order_combo.setCurrentText(str(detail.get("purchase_order_number") or ""))
        self.purchase_order_combo.setEnabled(False)
        self.supplier_input.setText(str(detail.get("supplier_name") or ""))
        self.warehouse_input.setText(str(detail.get("warehouse") or ""))
        date_value = QDate.fromString(str(detail.get("receipt_date") or ""), "yyyy-MM-dd")
        if date_value.isValid():
            self.receipt_date_input.setDate(date_value)
        self.notes_input.setPlainText(str(detail.get("notes") or ""))

        self.product_table.blockSignals(True)
        self.product_table.setRowCount(0)
        for item in detail.get("items", []):
            row = self.product_table.rowCount()
            self.product_table.insertRow(row)

            stock_code_item = QTableWidgetItem(str(item.get("stock_code") or ""))
            stock_code_item.setFlags(stock_code_item.flags() & ~Qt.ItemIsEditable)
            stock_code_item.setData(Qt.UserRole, int(item.get("stock_id") or 0))
            stock_code_item.setData(Qt.UserRole + 1, int(item.get("purchase_order_item_id") or 0))
            self.product_table.setItem(row, self.COL_STOCK_CODE, stock_code_item)

            for col, key in [
                (self.COL_BARCODE, "barcode"),
                (self.COL_PRODUCT_NAME, "product_name"),
                (self.COL_ORDERED, "ordered_qty"),
                (self.COL_RECEIVED, "received_qty"),
                (self.COL_REMAINING, "remaining_qty"),
                (self.COL_UNIT, "unit"),
                (self.COL_WAREHOUSE, "warehouse"),
            ]:
                text = str(item.get(key) or "")
                widget_item = QTableWidgetItem(text)
                if col in (self.COL_BARCODE, self.COL_PRODUCT_NAME, self.COL_ORDERED, self.COL_REMAINING, self.COL_UNIT):
                    widget_item.setFlags(widget_item.flags() & ~Qt.ItemIsEditable)
                self.product_table.setItem(row, col, widget_item)

        self.product_table.blockSignals(False)
        self._update_totals()

    def _on_save(self):
        self._save_document(close_on_success=True)

    def _save_document(self, close_on_success: bool) -> bool:
        po = self._selected_purchase_order() if not self.is_edit_mode else None
        purchase_order_id = int(po.get("id") or 0) if po else 0
        supplier_id = int(po.get("supplier_id") or 0) if po else 0

        if self.is_edit_mode:
            detail = GoodsReceiptModel.receipt_detail(self.receipt_number_input.text().strip())
            if detail is not None:
                purchase_order_id = int(detail.get("purchase_order_id") or 0)
                supplier_id = int(detail.get("supplier_id") or 0)

        if purchase_order_id <= 0 or supplier_id <= 0:
            QMessageBox.warning(self, "Uyarı", "Satın alma siparişi seçimi zorunludur.")
            return False

        items_payload: List[Dict[str, Any]] = []
        positive_rows = 0
        for row in range(self.product_table.rowCount()):
            stock_item = self.product_table.item(row, self.COL_STOCK_CODE)
            if stock_item is None:
                continue
            stock_id = int(stock_item.data(Qt.UserRole) or 0)
            po_item_id = int(stock_item.data(Qt.UserRole + 1) or 0)
            ordered_qty = self._cell_float(row, self.COL_ORDERED, 0)
            received_qty = self._cell_float(row, self.COL_RECEIVED, 0)
            remaining_qty = self._cell_float(row, self.COL_REMAINING, 0)
            unit = self.product_table.item(row, self.COL_UNIT).text().strip() if self.product_table.item(row, self.COL_UNIT) else ""
            warehouse = self.product_table.item(row, self.COL_WAREHOUSE).text().strip() if self.product_table.item(row, self.COL_WAREHOUSE) else ""

            if received_qty > 0:
                positive_rows += 1

            items_payload.append(
                {
                    "purchase_order_item_id": po_item_id,
                    "stock_id": stock_id,
                    "ordered_qty": ordered_qty,
                    "received_qty": received_qty,
                    "remaining_qty": max(remaining_qty - received_qty, 0),
                    "unit": unit,
                    "warehouse": warehouse,
                }
            )

        if not self.is_edit_mode and positive_rows == 0:
            QMessageBox.warning(self, "Uyarı", "En az bir satırda teslim alınan miktar 0'dan büyük olmalıdır.")
            return False

        created_by = os.getenv("USERNAME") or os.getenv("USER") or "SYSTEM"

        try:
            GoodsReceiptModel.save_receipt(
                receipt_number=self.receipt_number_input.text().strip(),
                purchase_order_id=purchase_order_id,
                supplier_id=supplier_id,
                warehouse=self.warehouse_input.text().strip(),
                receipt_date=self.receipt_date_input.date().toString("yyyy-MM-dd"),
                notes=self.notes_input.toPlainText().strip(),
                items=items_payload,
                created_by=created_by,
                existing_receipt_number=self.receipt_number if self.is_edit_mode else None,
            )
            self.saved_receipt_number = self.receipt_number_input.text().strip()
            self.receipt_number = self.saved_receipt_number
            self.is_edit_mode = True
            self._has_persisted_document = True
            self._last_saved_signature = build_template_signature(self._build_preview_template())
            if close_on_success:
                self.accept()
            return True
        except Exception as exc:
            QMessageBox.critical(self, "Hata", f"Mal kabul kaydı kaydedilemedi:\n{exc}")
            return False

    def _initialize_preview_state(self):
        if self._has_persisted_document:
            self._last_saved_signature = build_template_signature(self._build_preview_template())

    def _has_unsaved_changes(self) -> bool:
        if not self._has_persisted_document:
            return False
        current = build_template_signature(self._build_preview_template())
        return current != self._last_saved_signature

    def _get_preview_controller(self) -> DocumentPreviewController:
        if self._preview_controller is None:
            self._preview_controller = DocumentPreviewController(
                parent=self,
                has_saved_document=lambda: self._has_persisted_document,
                has_unsaved_changes=self._has_unsaved_changes,
                save_callback=self._save_document,
                template_provider=self._build_preview_template,
            )
        return self._preview_controller

    def _on_preview(self):
        self._get_preview_controller().open_preview()

    def _build_preview_template(self) -> DocumentTemplate:
        supplier_name = self.supplier_input.text().strip()
        party = resolve_party_details(party_code="", party_name=supplier_name)

        items: list[DocumentLineItem] = []
        subtotal = 0.0
        discount_total = 0.0
        vat_total = 0.0

        for row in range(self.product_table.rowCount()):
            stock_code = self.product_table.item(row, self.COL_STOCK_CODE).text().strip() if self.product_table.item(row, self.COL_STOCK_CODE) else ""
            if not stock_code:
                continue

            received_qty = self._cell_float(row, self.COL_RECEIVED, 0)
            if received_qty <= 0:
                continue

            description = self.product_table.item(row, self.COL_PRODUCT_NAME).text().strip() if self.product_table.item(row, self.COL_PRODUCT_NAME) else ""
            unit = self.product_table.item(row, self.COL_UNIT).text().strip() if self.product_table.item(row, self.COL_UNIT) else ""

            subtotal += received_qty

            items.append(
                DocumentLineItem(
                    line_no=len(items) + 1,
                    product_code=stock_code,
                    description=description,
                    quantity=f"{received_qty:.3f}".rstrip("0").rstrip("."),
                    unit=unit,
                    unit_price="0.00",
                    discount="0.00%",
                    vat="0.00%",
                    total=f"{received_qty:.3f}".rstrip("0").rstrip("."),
                )
            )

        grand_total = subtotal - discount_total + vat_total
        return DocumentTemplate(
            document_title="GOODS RECEIPT",
            filename_base=(self.receipt_number_input.text().strip() or "goods_receipt").replace("/", "-"),
            invoice_number=self.receipt_number_input.text().strip(),
            invoice_date=self.receipt_date_input.date().toString("yyyy-MM-dd"),
            customer_name=party.get("name") or supplier_name,
            customer_company_name=party.get("name") or supplier_name,
            customer_address=party.get("address") or "",
            customer_country=party.get("country") or "",
            customer_tax_number=party.get("tax_number") or "",
            customer_phone=party.get("phone") or "",
            customer_email=party.get("email") or "",
            customer_whatsapp=party.get("phone") or "",
            subtotal=f"{subtotal:.2f}",
            discount_total=f"{discount_total:.2f}",
            vat_total=f"{vat_total:.2f}",
            grand_total=f"{grand_total:.2f}",
            items=items,
        )

    def get_saved_receipt_number(self) -> Optional[str]:
        return self.saved_receipt_number or None
