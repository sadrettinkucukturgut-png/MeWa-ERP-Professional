import os
from pathlib import Path
from typing import Dict, List, Optional

from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDateEdit,
    QDialog,
    QDoubleSpinBox,
    QFrame,
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

from models.purchase_order_model import PurchaseOrderModel
from models.stock_model import StockModel
from models.supplier_model import SupplierModel
from services.document_preview_engine import (
    DocumentLineItem,
    DocumentPreviewController,
    DocumentTemplate,
    build_template_signature,
    resolve_party_details,
)
from shared.widgets.stock_lookup_dialog import StockLookupDialog


class StockSelectionDialog(QDialog):
    def __init__(self, stocks: List[tuple], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Ürün Seç")
        self.resize(860, 520)
        self._stocks = stocks
        self.selected_stock: Optional[Dict[str, str]] = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Stok kodu, barkod veya ürün adı ara")
        self.search_input.textChanged.connect(self._fill_table)
        layout.addWidget(self.search_input)

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Stok Kodu", "Barkod", "Ürün Adı", "Birim"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(False)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.doubleClicked.connect(self._accept_selected)
        layout.addWidget(self.table)

        button_row = QHBoxLayout()
        button_row.addStretch()
        select_btn = QPushButton("Seç")
        select_btn.clicked.connect(self._accept_selected)
        cancel_btn = QPushButton("İptal")
        cancel_btn.clicked.connect(self.reject)
        button_row.addWidget(select_btn)
        button_row.addWidget(cancel_btn)
        layout.addLayout(button_row)

        self._fill_table("")

    def _fill_table(self, text: str):
        token = (text or "").strip().lower()
        visible = []
        for stock in self._stocks:
            stock_code = str(stock[0] or "")
            barcode = str(stock[1] or "")
            product_name = str(stock[2] or "")
            unit = str(stock[6] or "")
            if token and token not in f"{stock_code} {barcode} {product_name}".lower():
                continue
            visible.append((stock_code, barcode, product_name, unit, stock))

        self.table.setRowCount(len(visible))
        for row, data in enumerate(visible):
            for col, value in enumerate(data[:4]):
                self.table.setItem(row, col, QTableWidgetItem(value))
            self.table.setVerticalHeaderItem(row, QTableWidgetItem(str(data[4][0] or "")))

    def _accept_selected(self):
        row = self.table.currentRow()
        if row < 0:
            return
        stock_code = self.table.item(row, 0).text().strip() if self.table.item(row, 0) else ""
        stock = StockModel.getir(stock_code)
        if not stock:
            return

        self.selected_stock = {
            "stock_code": str(stock[0] or ""),
            "barcode": str(stock[1] or ""),
            "product_name": str(stock[2] or ""),
            "unit": str(stock[6] or ""),
            "unit_price": str(stock[7] or 0),
        }
        self.accept()


class NewPurchaseOrderDialog(QDialog):
    COL_STOCK_CODE = 0
    COL_BARCODE = 1
    COL_PRODUCT_NAME = 2
    COL_UNIT = 3
    COL_QUANTITY = 4
    COL_UNIT_PRICE = 5
    COL_DISCOUNT = 6
    COL_VAT = 7
    COL_LINE_TOTAL = 8

    def __init__(self, order_number: Optional[str] = None, parent=None):
        super().__init__(parent)
        self.order_number = order_number
        self.is_edit_mode = bool(order_number)
        self.saved_order_number = ""
        self._supplier_map: Dict[str, int] = {}
        self._stock_map: Dict[str, int] = {}
        self._preview_controller: Optional[DocumentPreviewController] = None
        self._has_persisted_document = self.is_edit_mode
        self._last_saved_signature = ""

        self.setWindowTitle("Satın Alma Siparişi Düzenle" if self.is_edit_mode else "Yeni Satın Alma Siparişi")
        self.resize(1180, 860)
        self._setup_ui()
        self._load_suppliers()
        self._load_stocks()

        if self.is_edit_mode and order_number:
            self._load_order_data(order_number)
        else:
            self.order_no_input.setText(PurchaseOrderModel.siparis_numarasi_uret())
            self._update_totals()

        self._initialize_preview_state()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setFrameShape(QScrollArea.NoFrame)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(20, 20, 20, 20)
        content_layout.setSpacing(14)

        title = QLabel("🧾 Satın Alma Siparişi")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #f8fafc;")
        content_layout.addWidget(title)

        self.logo_label = QLabel()
        self.logo_label.setAlignment(Qt.AlignRight)
        self._load_logo()
        content_layout.addWidget(self.logo_label)

        form_widget = QWidget()
        form_layout = QFormLayout(form_widget)
        form_layout.setLabelAlignment(Qt.AlignLeft)
        form_layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)

        self.order_no_input = QLineEdit()
        self.order_no_input.setReadOnly(True)

        self.supplier_combo = QComboBox()
        self.supplier_combo.setEditable(True)
        self.supplier_combo.setInsertPolicy(QComboBox.NoInsert)

        self.order_date_input = QDateEdit()
        self.order_date_input.setCalendarPopup(True)
        self.order_date_input.setDate(QDate.currentDate())

        self.delivery_date_input = QDateEdit()
        self.delivery_date_input.setCalendarPopup(True)
        self.delivery_date_input.setDate(QDate.currentDate())

        self.currency_combo = QComboBox()
        self.currency_combo.addItems(["USD", "EUR", "TRY", "AED", "SAR", "GBP", "CNY", "RUB"])
        self.currency_combo.setCurrentText("USD")

        self.exchange_rate_input = QDoubleSpinBox()
        self.exchange_rate_input.setDecimals(6)
        self.exchange_rate_input.setMinimum(0.000001)
        self.exchange_rate_input.setMaximum(999999)
        self.exchange_rate_input.setValue(1.0)

        self.status_combo = QComboBox()
        self.status_combo.addItem("Taslak", "Draft")
        self.status_combo.addItem("Onaylı", "Approved")
        self.status_combo.addItem("İptal", "Cancelled")
        self.status_combo.setCurrentIndex(0)

        self.reference_no_input = QLineEdit()

        self.notes_input = QTextEdit()
        self.notes_input.setFixedHeight(84)

        form_layout.addRow("Sipariş Numarası", self.order_no_input)
        form_layout.addRow("Tedarikçi", self.supplier_combo)
        form_layout.addRow("Sipariş Tarihi", self.order_date_input)
        form_layout.addRow("Teslim Tarihi", self.delivery_date_input)
        form_layout.addRow("Para Birimi", self.currency_combo)
        form_layout.addRow("Kur", self.exchange_rate_input)
        form_layout.addRow("Durum", self.status_combo)
        form_layout.addRow("Referans No", self.reference_no_input)
        form_layout.addRow("Notlar", self.notes_input)

        content_layout.addWidget(form_widget)

        product_button_row = QHBoxLayout()
        self.add_product_button = QPushButton("Ürün Ekle")
        self.add_product_button.clicked.connect(self._select_and_add_product)
        self.remove_product_button = QPushButton("Ürün Sil")
        self.remove_product_button.clicked.connect(self._remove_selected_product_row)
        product_button_row.addWidget(self.add_product_button)
        product_button_row.addWidget(self.remove_product_button)
        product_button_row.addStretch()
        content_layout.addLayout(product_button_row)

        self.product_table = QTableWidget()
        self.product_table.setColumnCount(9)
        self.product_headers = [
            "Stok Kodu",
            "Barkod",
            "Ürün Adı",
            "Birim",
            "Miktar",
            "Birim Fiyat",
            "İskonto %",
            "KDV %",
            "Satır Toplamı",
        ]
        self.product_table.setHorizontalHeaderLabels(self.product_headers)
        self.product_table.setAlternatingRowColors(True)
        self.product_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.product_table.setSelectionMode(QTableWidget.SingleSelection)
        self.product_table.setSortingEnabled(False)
        self.product_table.verticalHeader().setVisible(False)
        self.product_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.product_table.horizontalHeader().setStretchLastSection(False)
        self.product_table.horizontalHeader().setSectionsMovable(False)
        self.product_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.product_table.itemChanged.connect(self._on_product_item_changed)

        self.product_table.setStyleSheet(
            "QTableWidget {background:#111827; alternate-background-color:#0f172a; color:#e5e7eb;"
            "gridline-color:#1f2937; border:1px solid #334155; border-radius:10px;}"
            "QHeaderView::section {background:#1f2937; color:#e5e7eb; padding:8px 6px; border:1px solid #111827;}"
            "QTableWidget::item:selected {background:#2563eb; color:white;}"
            "QTableWidget::item:hover {background:#1e293b;}"
        )
        content_layout.addWidget(self.product_table)

        totals_frame = QFrame()
        totals_frame.setStyleSheet(
            "QFrame{background:#0f172a; border:1px solid #334155; border-radius:10px;}"
        )
        totals_layout = QGridLayout(totals_frame)
        totals_layout.setContentsMargins(12, 10, 12, 10)
        totals_layout.setHorizontalSpacing(12)
        totals_layout.setVerticalSpacing(8)

        self.subtotal_value = QLabel("0.00")
        self.discount_value = QLabel("0.00")
        self.vat_value = QLabel("0.00")
        self.grand_total_value = QLabel("0.00")

        for label in [self.subtotal_value, self.discount_value, self.vat_value, self.grand_total_value]:
            label.setStyleSheet("font-size:14px; font-weight:700; color:#f8fafc;")
            label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        totals_layout.addWidget(QLabel("Ara Toplam"), 0, 0)
        totals_layout.addWidget(self.subtotal_value, 0, 1)
        totals_layout.addWidget(QLabel("İskonto"), 1, 0)
        totals_layout.addWidget(self.discount_value, 1, 1)
        totals_layout.addWidget(QLabel("KDV"), 2, 0)
        totals_layout.addWidget(self.vat_value, 2, 1)
        totals_layout.addWidget(QLabel("Genel Toplam"), 3, 0)
        totals_layout.addWidget(self.grand_total_value, 3, 1)

        content_layout.addWidget(totals_frame)

        button_row = QHBoxLayout()
        button_row.addStretch()

        self.preview_btn = QPushButton("Önizleme")
        self.preview_btn.clicked.connect(self._on_preview)
        self.save_btn = QPushButton("Kaydet")
        self.save_btn.setDefault(True)
        self.save_btn.clicked.connect(self._on_save)
        self.cancel_btn = QPushButton("İptal")
        self.cancel_btn.clicked.connect(self.reject)

        button_row.addWidget(self.preview_btn)
        button_row.addWidget(self.save_btn)
        button_row.addWidget(self.cancel_btn)
        content_layout.addLayout(button_row)

        scroll_area.setWidget(content)
        root.addWidget(scroll_area)

        self.setStyleSheet(
            "QDialog{background:#0b1220;} QLabel{color:#e2e8f0;}"
            "QLineEdit,QComboBox,QDateEdit,QTextEdit,QDoubleSpinBox{"
            "background:#0f172a; color:#e2e8f0; border:1px solid #334155; border-radius:8px; padding:6px;}"
            "QPushButton{background:#1e293b; color:#f8fafc; border:1px solid #334155; border-radius:8px; padding:8px 12px;}"
            "QPushButton:hover{background:#334155;}"
        )

    def _resolve_logo_path(self) -> Path:
        project_root = Path(__file__).resolve().parent.parent
        official_logo = project_root / "assets" / "logos" / "mewa_logo.png"
        fallback_logo = project_root / "assets" / "logo.png"
        return official_logo if official_logo.exists() else fallback_logo

    def _load_logo(self):
        logo_path = self._resolve_logo_path()
        if not logo_path.exists():
            self.logo_label.clear()
            return

        pixmap = QPixmap(str(logo_path))
        if pixmap.isNull():
            self.logo_label.clear()
            return

        self.logo_label.setPixmap(pixmap.scaled(180, 70, Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def _load_suppliers(self):
        self._supplier_map = {}
        self.supplier_combo.clear()
        try:
            suppliers = SupplierModel.tum_tedarikciler()
            self.supplier_combo.addItem("")
            for supplier in suppliers:
                company_name = str(supplier.get("company_name") or "").strip()
                supplier_id = int(supplier.get("id") or 0)
                if company_name:
                    self.supplier_combo.addItem(company_name)
                    self._supplier_map[company_name] = supplier_id
        except Exception:
            self.supplier_combo.addItem("")

    def _load_stocks(self):
        self._stock_map = {}
        try:
            for stock in StockModel.tum_stoklar():
                stock_id = self._get_stock_id_by_code(str(stock[0] or ""))
                if stock_id is not None:
                    self._stock_map[str(stock[0] or "")] = stock_id
        except Exception:
            self._stock_map = {}

    def _get_stock_id_by_code(self, stock_code: str) -> Optional[int]:
        if not stock_code:
            return None
        from sqlite3 import connect

        db_path = Path(__file__).resolve().parent.parent / "database" / "mewa.db"
        with connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM stoklar WHERE stock_code = ?", (stock_code,))
            row = cursor.fetchone()
            if row is None:
                return None
            return int(row[0])

    def _load_order_data(self, order_number: str):
        order = PurchaseOrderModel.detay_getir(order_number)
        if order is None:
            QMessageBox.warning(self, "Uyarı", "Satın alma siparişi bulunamadı.")
            self.reject()
            return

        self.order_no_input.setText(str(order.get("order_number") or ""))
        supplier_name = str(order.get("supplier_name") or "")
        self.supplier_combo.setCurrentText(supplier_name)

        self.order_date_input.setDate(QDate.fromString(str(order.get("order_date") or ""), "yyyy-MM-dd"))
        delivery = QDate.fromString(str(order.get("delivery_date") or ""), "yyyy-MM-dd")
        if delivery.isValid():
            self.delivery_date_input.setDate(delivery)
        self.currency_combo.setCurrentText(str(order.get("currency") or "USD"))
        self.exchange_rate_input.setValue(float(order.get("exchange_rate") or 1.0))
        status_value = str(order.get("status") or "Draft")
        status_index = self.status_combo.findData(status_value)
        if status_index < 0:
            status_index = self.status_combo.findText(status_value)
        if status_index >= 0:
            self.status_combo.setCurrentIndex(status_index)
        self.reference_no_input.setText(str(order.get("reference_no") or ""))
        self.notes_input.setPlainText(str(order.get("notes") or ""))

        self.product_table.blockSignals(True)
        self.product_table.setRowCount(0)
        for item in order.get("items", []):
            self._append_product_row(
                stock_code=str(item.get("stock_code") or ""),
                barcode=str(item.get("barcode") or ""),
                product_name=str(item.get("product_name") or ""),
                unit=str(item.get("unit") or ""),
                quantity=float(item.get("quantity") or 0),
                unit_price=float(item.get("unit_price") or 0),
                discount=float(item.get("discount_percent") or 0),
                vat=float(item.get("vat_percent") or 0),
            )
        self.product_table.blockSignals(False)
        self._update_totals()

    def _select_and_add_product(self):
        selected = StockLookupDialog.select_stock(self)
        if not selected:
            return

        self._append_product_row(
            stock_code=str(selected.get("stock_code") or ""),
            barcode=str(selected.get("barcode") or ""),
            product_name=str(selected.get("product_name") or ""),
            unit=str(selected.get("unit") or ""),
            quantity=1.0,
            unit_price=float(selected.get("purchase_price_default") or selected.get("unit_price") or 0),
            discount=0.0,
            vat=0.0,
        )
        self._update_totals()

    def _append_product_row(
        self,
        stock_code: str,
        barcode: str,
        product_name: str,
        unit: str,
        quantity: float,
        unit_price: float,
        discount: float,
        vat: float,
    ):
        row = self.product_table.rowCount()
        self.product_table.insertRow(row)

        values = [
            stock_code,
            barcode,
            product_name,
            unit,
            f"{quantity:.3f}".rstrip("0").rstrip("."),
            f"{unit_price:.2f}",
            f"{discount:.2f}".rstrip("0").rstrip("."),
            f"{vat:.2f}".rstrip("0").rstrip("."),
            "0.00",
        ]

        for col, value in enumerate(values):
            item = QTableWidgetItem(value)
            if col in (self.COL_STOCK_CODE, self.COL_BARCODE, self.COL_PRODUCT_NAME, self.COL_UNIT):
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            if col == self.COL_LINE_TOTAL:
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.product_table.setItem(row, col, item)

        self._recalculate_row(row)

    def _add_product_row(self):
        row = self.product_table.rowCount()
        self.product_table.blockSignals(True)
        self.product_table.insertRow(row)

        defaults = ["", "", "", "PCS", "1", "0.00", "0", "0", "0.00"]
        for col, value in enumerate(defaults):
            item = QTableWidgetItem(value)
            if col in (self.COL_STOCK_CODE, self.COL_BARCODE, self.COL_PRODUCT_NAME, self.COL_UNIT):
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            if col == self.COL_LINE_TOTAL:
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.product_table.setItem(row, col, item)

        self.product_table.blockSignals(False)
        self._recalculate_row(row)
        self._update_totals()

    def _remove_selected_product_row(self):
        row = self.product_table.currentRow()
        if row < 0:
            return
        self.product_table.removeRow(row)
        self._update_totals()

    def _on_product_item_changed(self, item):
        if item is None:
            return
        self._recalculate_row(item.row())
        self._update_totals()

    def _recalculate_row(self, row: int):
        qty = self._cell_float(row, self.COL_QUANTITY, 0.0)
        unit_price = self._cell_float(row, self.COL_UNIT_PRICE, 0.0)
        discount_percent = self._cell_float(row, self.COL_DISCOUNT, 0.0)
        vat_percent = self._cell_float(row, self.COL_VAT, 0.0)

        base_amount = qty * unit_price
        discount_amount = base_amount * (discount_percent / 100.0)
        net_amount = base_amount - discount_amount
        vat_amount = net_amount * (vat_percent / 100.0)
        line_total = net_amount + vat_amount

        self.product_table.blockSignals(True)
        line_item = self.product_table.item(row, self.COL_LINE_TOTAL)
        if line_item is None:
            line_item = QTableWidgetItem()
            line_item.setFlags(line_item.flags() & ~Qt.ItemIsEditable)
            line_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.product_table.setItem(row, self.COL_LINE_TOTAL, line_item)
        line_item.setText(f"{line_total:.2f}")
        self.product_table.blockSignals(False)

    def _cell_float(self, row: int, col: int, default: float) -> float:
        item = self.product_table.item(row, col)
        if item is None:
            return default
        try:
            return float(item.text().strip() or default)
        except ValueError:
            return default

    def _update_totals(self):
        subtotal = 0.0
        discount = 0.0
        vat = 0.0

        for row in range(self.product_table.rowCount()):
            qty = self._cell_float(row, self.COL_QUANTITY, 0.0)
            unit_price = self._cell_float(row, self.COL_UNIT_PRICE, 0.0)
            discount_percent = self._cell_float(row, self.COL_DISCOUNT, 0.0)
            vat_percent = self._cell_float(row, self.COL_VAT, 0.0)

            base = qty * unit_price
            disc = base * (discount_percent / 100.0)
            net = base - disc
            vat_amount = net * (vat_percent / 100.0)

            subtotal += base
            discount += disc
            vat += vat_amount

        grand_total = subtotal - discount + vat
        self.subtotal_value.setText(f"{subtotal:,.2f}")
        self.discount_value.setText(f"{discount:,.2f}")
        self.vat_value.setText(f"{vat:,.2f}")
        self.grand_total_value.setText(f"{grand_total:,.2f}")

    def _on_save(self):
        self._save_document(close_on_success=True)

    def _save_document(self, close_on_success: bool) -> bool:
        supplier_name = self.supplier_combo.currentText().strip()
        supplier_id = self._supplier_map.get(supplier_name)
        if not supplier_id:
            QMessageBox.warning(self, "Uyarı", "Tedarikçi seçimi zorunludur.")
            return False
        if self.product_table.rowCount() == 0:
            QMessageBox.warning(self, "Uyarı", "En az bir ürün eklenmelidir.")
            return False

        items: List[Dict[str, float]] = []
        for row in range(self.product_table.rowCount()):
            stock_code_item = self.product_table.item(row, self.COL_STOCK_CODE)
            stock_code = stock_code_item.text().strip() if stock_code_item else ""
            stock_id = self._stock_map.get(stock_code)
            if not stock_id:
                QMessageBox.warning(self, "Uyarı", f"{row + 1}. satırda geçersiz stok var.")
                return False

            items.append(
                {
                    "stock_id": stock_id,
                    "unit": self.product_table.item(row, self.COL_UNIT).text().strip() if self.product_table.item(row, self.COL_UNIT) else "",
                    "quantity": self._cell_float(row, self.COL_QUANTITY, 0.0),
                    "unit_price": self._cell_float(row, self.COL_UNIT_PRICE, 0.0),
                    "discount_percent": self._cell_float(row, self.COL_DISCOUNT, 0.0),
                    "vat_percent": self._cell_float(row, self.COL_VAT, 0.0),
                    "line_total": self._cell_float(row, self.COL_LINE_TOTAL, 0.0),
                }
            )

        try:
            PurchaseOrderModel.kaydet(
                order_number=self.order_no_input.text().strip(),
                supplier_id=supplier_id,
                order_date=self.order_date_input.date().toString("yyyy-MM-dd"),
                delivery_date=self.delivery_date_input.date().toString("yyyy-MM-dd"),
                currency=self.currency_combo.currentText(),
                exchange_rate=float(self.exchange_rate_input.value()),
                status=str(self.status_combo.currentData() or self.status_combo.currentText()),
                reference_no=self.reference_no_input.text().strip(),
                notes=self.notes_input.toPlainText().strip(),
                items=items,
                existing_order_number=self.order_number if self.is_edit_mode else None,
            )
            self.saved_order_number = self.order_no_input.text().strip()
            self.order_number = self.saved_order_number
            self.is_edit_mode = True
            self._has_persisted_document = True
            self._last_saved_signature = build_template_signature(self._build_preview_template())
            if close_on_success:
                self.accept()
            return True
        except Exception as exc:
            QMessageBox.critical(self, "Hata", f"Satın alma siparişi kaydedilemedi:\n{exc}")
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
        supplier_name = self.supplier_combo.currentText().strip()
        party = resolve_party_details(party_code="", party_name=supplier_name)

        items: list[DocumentLineItem] = []
        subtotal = 0.0
        discount_total = 0.0
        vat_total = 0.0

        for row in range(self.product_table.rowCount()):
            stock_code = self.product_table.item(row, self.COL_STOCK_CODE).text().strip() if self.product_table.item(row, self.COL_STOCK_CODE) else ""
            if not stock_code:
                continue

            qty = self._cell_float(row, self.COL_QUANTITY, 0.0)
            unit_price = self._cell_float(row, self.COL_UNIT_PRICE, 0.0)
            discount_percent = self._cell_float(row, self.COL_DISCOUNT, 0.0)
            vat_percent = self._cell_float(row, self.COL_VAT, 0.0)

            base = qty * unit_price
            disc = base * (discount_percent / 100.0)
            net = base - disc
            vat_amount = net * (vat_percent / 100.0)
            line_total = net + vat_amount

            subtotal += base
            discount_total += disc
            vat_total += vat_amount

            unit = self.product_table.item(row, self.COL_UNIT).text().strip() if self.product_table.item(row, self.COL_UNIT) else ""
            description = self.product_table.item(row, self.COL_PRODUCT_NAME).text().strip() if self.product_table.item(row, self.COL_PRODUCT_NAME) else ""

            items.append(
                DocumentLineItem(
                    line_no=len(items) + 1,
                    product_code=stock_code,
                    description=description,
                    quantity=f"{qty:.3f}".rstrip("0").rstrip("."),
                    unit=unit,
                    unit_price=f"{unit_price:.2f}",
                    discount=f"{discount_percent:.2f}%",
                    vat=f"{vat_percent:.2f}%",
                    total=f"{line_total:.2f}",
                )
            )

        grand_total = subtotal - discount_total + vat_total
        return DocumentTemplate(
            document_title="PURCHASE ORDER",
            filename_base=(self.order_no_input.text().strip() or "purchase_order").replace("/", "-"),
            invoice_number=self.order_no_input.text().strip(),
            invoice_date=self.order_date_input.date().toString("yyyy-MM-dd"),
            currency=self.currency_combo.currentText().strip() or "USD",
            exchange_rate=str(self.exchange_rate_input.value()),
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

    def get_saved_order_number(self) -> Optional[str]:
        if not self.saved_order_number:
            return None
        return self.saved_order_number
