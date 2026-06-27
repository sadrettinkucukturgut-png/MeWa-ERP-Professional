import os
from typing import Any, Dict, List, Optional

from PySide6.QtCore import QDate, QEvent, Qt
from PySide6.QtGui import QColor, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QDateEdit,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHeaderView,
    QHBoxLayout,
    QGraphicsDropShadowEffect,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QLayout,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QToolButton,
    QStyledItemDelegate,
    QVBoxLayout,
    QWidget,
)

from models.purchase_invoice_model import PurchaseInvoiceModel
from shared.widgets.cari_lookup_dialog import CariLookupDialog
from shared.widgets.stock_lookup_dialog import StockLookupDialog


class PurchaseInvoiceItemDelegate(QStyledItemDelegate):
    def createEditor(self, parent, option, index):
        editor = super().createEditor(parent, option, index)
        if editor is not None:
            editor.installEventFilter(self)
        return editor

    def eventFilter(self, editor, event):
        if event.type() == QEvent.KeyPress and event.key() in (Qt.Key_Return, Qt.Key_Enter):
            table = self.parent()
            handler = table.window() if table is not None else None
            if handler is not None and hasattr(handler, "_handle_editor_enter"):
                self.commitData.emit(editor)
                self.closeEditor.emit(editor, QStyledItemDelegate.NoHint)
                handler._handle_editor_enter()
                return True
        return super().eventFilter(editor, event)


class PurchaseInvoiceGrid(QTableWidget):
    def keyPressEvent(self, event):
        handler = self.window()
        if handler is not None and hasattr(handler, "_handle_grid_key_press"):
            if handler._handle_grid_key_press(event):
                return
        super().keyPressEvent(event)


class NewPurchaseInvoiceDialog(QDialog):
    COL_ROW_NO = 0
    COL_STOCK_CODE = 1
    COL_PRODUCT = 2
    COL_QTY = 3
    COL_UNIT = 4
    COL_UNIT_PRICE = 5
    COL_DISCOUNT = 6
    COL_VAT = 7
    COL_LINE_TOTAL = 8

    def __init__(self, invoice_number: Optional[str] = None, parent=None):
        super().__init__(parent)
        self.invoice_number = invoice_number
        self.is_edit_mode = bool(invoice_number)
        self.saved_invoice_number = ""

        self._receipt_map: Dict[str, Dict[str, Any]] = {}
        self._selected_cari_record: Optional[Dict[str, Any]] = None
        self._selected_stock_row: Optional[int] = None
        self._row_visible_count = 10

        self.setWindowTitle("Alış Faturası Düzenle" if self.is_edit_mode else "Yeni Alış Faturası")
        available = QApplication.primaryScreen().availableGeometry() if QApplication.primaryScreen() else None
        if available is not None:
            width = max(900, min(1180, int(available.width() * 0.92)))
            height = max(620, min(860, int(available.height() * 0.9)))
            self.resize(width, height)
        else:
            self.resize(1180, 860)

        self._setup_ui()

        if self.is_edit_mode and invoice_number:
            self._load_invoice(invoice_number)
        else:
            self.invoice_number_input.setText(PurchaseInvoiceModel.invoice_number_generate())
            self.invoice_date_input.setDate(QDate.currentDate())
            self.due_date_input.setDate(QDate.currentDate())
            self._add_product_row()
            self._update_totals()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setFrameShape(QScrollArea.NoFrame)

        content = QWidget()
        content.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(20, 20, 20, 20)
        content_layout.setSpacing(14)
        content_layout.setSizeConstraint(QLayout.SetMinimumSize)

        title = QLabel("🧾 Alış Faturası")
        title.setStyleSheet("font-size:20px; font-weight:bold; color:#f8fafc;")
        content_layout.addWidget(title)

        form_widget = QWidget()
        form_layout = QFormLayout(form_widget)
        form_layout.setLabelAlignment(Qt.AlignLeft)
        form_layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)

        self.invoice_number_input = QLineEdit()

        self.cari_input = QLineEdit()
        self.cari_input.setReadOnly(True)
        self.cari_input.installEventFilter(self)
        self.supplier_input = self.cari_input

        self.cari_lookup_button = QToolButton()
        self.cari_lookup_button.setText("...")
        self.cari_lookup_button.setCursor(Qt.PointingHandCursor)
        self.cari_lookup_button.setFixedWidth(30)
        self.cari_lookup_button.setStyleSheet(
            "QToolButton{background:#1e293b; color:#f8fafc; border:1px solid #334155; border-radius:8px;}"
            "QToolButton:hover{background:#334155;}"
        )
        self.cari_lookup_button.clicked.connect(self._open_cari_lookup)

        cari_widget = QWidget()
        cari_layout = QHBoxLayout(cari_widget)
        cari_layout.setContentsMargins(0, 0, 0, 0)
        cari_layout.setSpacing(6)
        cari_layout.addWidget(self.cari_input, 1)
        cari_layout.addWidget(self.cari_lookup_button, 0)

        self.cari_kodu_input = QLineEdit()
        self.cari_kodu_input.setReadOnly(True)

        self.company_name_input = QLineEdit()
        self.company_name_input.setReadOnly(True)

        self.payment_term_input = QLineEdit()
        self.payment_term_input.setReadOnly(True)
        self.payment_term_input.hide()

        self.purchase_order_input = QLineEdit()
        self.purchase_order_input.hide()

        self.invoice_date_input = QDateEdit()
        self.invoice_date_input.setCalendarPopup(True)

        self.due_date_input = QDateEdit()
        self.due_date_input.setCalendarPopup(True)

        self.currency_combo = QComboBox()
        self.currency_combo.addItems(["USD", "EUR", "TRY", "AED", "SAR", "GBP", "CNY", "RUB"])
        self.currency_combo.setCurrentText("USD")

        self.exchange_rate_input = QDoubleSpinBox()
        self.exchange_rate_input.setDecimals(6)
        self.exchange_rate_input.setMinimum(0.000001)
        self.exchange_rate_input.setMaximum(999999)
        self.exchange_rate_input.setValue(1.0)

        self.notes_input = QTextEdit()

        form_layout.addRow("Fatura No", self.invoice_number_input)
        form_layout.addRow("Cari", cari_widget)
        form_layout.addRow("Cari Kodu", self.cari_kodu_input)
        form_layout.addRow("Firma Ünvanı", self.company_name_input)
        form_layout.addRow("Fatura Tarihi", self.invoice_date_input)
        form_layout.addRow("Vade Tarihi", self.due_date_input)
        form_layout.addRow("Para Birimi", self.currency_combo)
        form_layout.addRow("Kur", self.exchange_rate_input)
        form_layout.addRow("Notlar", self.notes_input)

        content_layout.addWidget(form_widget)

        self.product_table = PurchaseInvoiceGrid(self)
        self.product_table.setColumnCount(9)
        self.product_table.setHorizontalHeaderLabels(
            [
                "#",
                "Stok Kodu",
                "Ürün",
                "Miktar",
                "Birim",
                "Birim Fiyat",
                "İskonto %",
                "KDV %",
                "Satır Toplamı",
            ]
        )
        self.product_table.setAlternatingRowColors(True)
        self.product_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.product_table.setSelectionMode(QTableWidget.SingleSelection)
        self.product_table.setSortingEnabled(False)
        self.product_table.verticalHeader().setVisible(False)
        self.product_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.product_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.product_table.horizontalHeader().setStretchLastSection(False)
        self.product_table.itemChanged.connect(self._on_product_item_changed)
        self.product_table.cellDoubleClicked.connect(self._on_product_cell_double_clicked)

        product_button_row = QHBoxLayout()
        product_button_row.addStretch()

        self.add_product_button = QPushButton("Satır Ekle")
        self.add_product_button.clicked.connect(self._add_product_row)

        self.stock_lookup_button = QToolButton()
        self.stock_lookup_button.setText("...")
        self.stock_lookup_button.setToolTip("Stok Seç")
        self.stock_lookup_button.setCursor(Qt.PointingHandCursor)
        self.stock_lookup_button.setFixedWidth(30)
        self.stock_lookup_button.setStyleSheet(
            "QToolButton{background:#1e293b; color:#f8fafc; border:1px solid #334155; border-radius:8px;}"
            "QToolButton:hover{background:#334155;}"
        )
        self.stock_lookup_button.clicked.connect(self._open_stock_lookup)

        self.remove_product_button = QPushButton("Satır Sil")
        self.remove_product_button.clicked.connect(self._remove_selected_product_row)

        product_button_row.addWidget(self.stock_lookup_button)
        product_button_row.addWidget(self.add_product_button)
        product_button_row.addWidget(self.remove_product_button)
        content_layout.addLayout(product_button_row)

        self.product_table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.product_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.MinimumExpanding)
        self.product_table.verticalHeader().setDefaultSectionSize(34)
        self.product_table.verticalHeader().setSectionResizeMode(QHeaderView.Fixed)
        self.product_table.horizontalHeader().setDefaultAlignment(Qt.AlignCenter)
        self.product_table.setItemDelegate(PurchaseInvoiceItemDelegate(self.product_table))
        self.product_table.setColumnWidth(self.COL_ROW_NO, 42)
        self.product_table.setColumnWidth(self.COL_STOCK_CODE, 120)
        self.product_table.setColumnWidth(self.COL_QTY, 90)
        self.product_table.setColumnWidth(self.COL_UNIT, 80)
        self.product_table.setColumnWidth(self.COL_UNIT_PRICE, 110)
        self.product_table.setColumnWidth(self.COL_DISCOUNT, 95)
        self.product_table.setColumnWidth(self.COL_VAT, 90)
        self.product_table.setColumnWidth(self.COL_LINE_TOTAL, 120)
        content_layout.addWidget(self.product_table)

        totals_frame = QFrame()
        totals_frame.setStyleSheet("QFrame{background:#0f172a; border:1px solid #334155; border-radius:10px;}")
        totals_layout = QGridLayout(totals_frame)
        totals_layout.setContentsMargins(12, 10, 12, 10)
        totals_layout.setHorizontalSpacing(12)
        totals_layout.setVerticalSpacing(8)

        self.subtotal_value = QLabel("0.00")
        self.discount_value = QLabel("0.00")
        self.vat_value = QLabel("0.00")
        self.grand_total_value = QLabel("0.00")

        for value_label in [self.subtotal_value, self.discount_value, self.vat_value, self.grand_total_value]:
            value_label.setStyleSheet("font-size:14px; font-weight:700; color:#f8fafc;")
            value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

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
        self.save_btn = QPushButton("Kaydet")
        self.save_btn.setDefault(True)
        self.save_btn.clicked.connect(self._on_save)
        self.cancel_btn = QPushButton("İptal")
        self.cancel_btn.clicked.connect(self.reject)
        button_row.addWidget(self.save_btn)
        button_row.addWidget(self.cancel_btn)
        content_layout.addLayout(button_row)

        self.scroll_area.setWidget(content)
        root.addWidget(self.scroll_area)

        self.setStyleSheet(
            "QDialog{background:#0b1220;} QLabel{color:#e2e8f0;}"
            "QLineEdit,QComboBox,QDateEdit,QTextEdit,QDoubleSpinBox{"
            "background:#0f172a; color:#e2e8f0; border:1px solid #334155; border-radius:8px; padding:6px;}"
            "QLineEdit:focus,QComboBox:focus,QDateEdit:focus,QTextEdit:focus,QDoubleSpinBox:focus,QTableWidget:focus{"
            "border:1px solid #f97316;"
            "background:#111827;"
            "}"
            "QPushButton{background:#1e293b; color:#f8fafc; border:1px solid #334155; border-radius:8px; padding:8px 12px;}"
            "QPushButton:hover{background:#334155;}"
            "QTableWidget{background:#111827; alternate-background-color:#0f172a; color:#e5e7eb; border:1px solid #334155;}"
            "QTableWidget::item:selected{background:#7db7ff; color:#ffffff;}"
            "QTableWidget::item:hover{background:#20364f; color:#e5e7eb;}"
            "QTableWidget::item:focus{border:1px solid #f97316;}"
            "QTableWidget::item:selected:focus{border:1px solid #f97316;}"
            "QHeaderView::section{background:#1f2937; color:#e5e7eb; padding:8px 6px;}"
        )

        self.setTabOrder(self.invoice_number_input, self.cari_input)
        self.setTabOrder(self.cari_input, self.cari_kodu_input)
        self.setTabOrder(self.cari_kodu_input, self.company_name_input)
        self.setTabOrder(self.company_name_input, self.invoice_date_input)
        self.setTabOrder(self.invoice_date_input, self.due_date_input)
        self.setTabOrder(self.due_date_input, self.currency_combo)
        self.setTabOrder(self.currency_combo, self.exchange_rate_input)
        self.setTabOrder(self.exchange_rate_input, self.notes_input)
        self.setTabOrder(self.notes_input, self.product_table)
        self.setTabOrder(self.product_table, self.save_btn)

        self.setFocusProxy(self.invoice_number_input)
        self.invoice_number_input.setFocus()
        self.installEventFilter(self)
        self.product_table.installEventFilter(self)
        self.product_table.viewport().installEventFilter(self)
        self.product_table.setFocusPolicy(Qt.StrongFocus)
        self.cari_input.setFocusPolicy(Qt.StrongFocus)
        self.cari_lookup_button.setFocusPolicy(Qt.StrongFocus)
        self.invoice_date_input.setFocusPolicy(Qt.StrongFocus)
        self.due_date_input.setFocusPolicy(Qt.StrongFocus)
        self.currency_combo.setFocusPolicy(Qt.StrongFocus)
        self.exchange_rate_input.setFocusPolicy(Qt.StrongFocus)
        self.notes_input.setFocusPolicy(Qt.StrongFocus)

        self._focus_targets = [
            self.invoice_number_input,
            self.cari_input,
            self.cari_lookup_button,
            self.cari_kodu_input,
            self.company_name_input,
            self.invoice_date_input,
            self.due_date_input,
            self.currency_combo,
            self.exchange_rate_input,
            self.notes_input,
            self.product_table,
            self.save_btn,
            self.cancel_btn,
            self.stock_lookup_button,
            self.add_product_button,
            self.remove_product_button,
        ]
        for widget in self._focus_targets:
            widget.installEventFilter(self)

        for widget in content.findChildren(QWidget):
            widget.installEventFilter(self)

        self._shortcut_save = QShortcut(QKeySequence("F5"), self)
        self._shortcut_save.setContext(Qt.WidgetWithChildrenShortcut)
        self._shortcut_save.activated.connect(self._on_save)
        self._shortcut_save_ctrl = QShortcut(QKeySequence("Ctrl+S"), self)
        self._shortcut_save_ctrl.setContext(Qt.WidgetWithChildrenShortcut)
        self._shortcut_save_ctrl.activated.connect(self._on_save)
        self._shortcut_edit = QShortcut(QKeySequence("F2"), self)
        self._shortcut_edit.setContext(Qt.WidgetWithChildrenShortcut)
        self._shortcut_edit.activated.connect(self._edit_current_cell)
        self._shortcut_print = QShortcut(QKeySequence("Ctrl+P"), self)
        self._shortcut_print.setContext(Qt.WidgetWithChildrenShortcut)
        self._shortcut_print.activated.connect(self._on_print_shortcut)
        self._shortcut_whatsapp = QShortcut(QKeySequence("Ctrl+W"), self)
        self._shortcut_whatsapp.setContext(Qt.WidgetWithChildrenShortcut)
        self._shortcut_whatsapp.activated.connect(self._on_whatsapp_shortcut)
        self._shortcut_close = QShortcut(QKeySequence("Esc"), self)
        self._shortcut_close.setContext(Qt.WidgetWithChildrenShortcut)
        self._shortcut_close.activated.connect(self.reject)

    def _supplier_record_by_id(self, supplier_id: int) -> Optional[Dict[str, Any]]:
        return CariLookupDialog.get_cari_by_supplier_id(supplier_id)

    def _apply_cari_record(self, record: Optional[Dict[str, Any]]):
        self._selected_cari_record = record
        if record is None:
            self.cari_input.clear()
            self.cari_kodu_input.clear()
            self.company_name_input.clear()
            self.payment_term_input.clear()
            return

        cari_text = str(record.get("firma_unvani") or record.get("company_name") or "")
        self.cari_input.setText(cari_text)
        self.cari_kodu_input.setText(str(record.get("cari_kodu") or ""))
        self.company_name_input.setText(cari_text)
        self.payment_term_input.setText(str(record.get("payment_term") or ""))

    def _open_cari_lookup(self):
        selected_cari = CariLookupDialog.select_cari(self)
        if selected_cari is None:
            return

        self._apply_cari_record(selected_cari)
        default_currency = str(selected_cari.get("default_currency") or "").strip()
        if default_currency:
            self.currency_combo.setCurrentText(default_currency)
        self.raise_()
        self.activateWindow()
        self.invoice_date_input.setFocus()

    def _open_stock_lookup(self):
        selected_stock = StockLookupDialog.select_stock(self)
        if selected_stock is None:
            return

        row = self.product_table.currentRow()
        if row < 0:
            row = self._selected_stock_row
        if row is None or row < 0 or row >= self.product_table.rowCount():
            row = self._add_product_row()

        self._fill_stock_row(row, selected_stock)
        self._selected_stock_row = row
        self._update_totals()
        self._focus_grid_cell(row, self.COL_QTY)

    def _fill_stock_row(self, row: int, stock: Dict[str, Any]):
        self._ensure_row_items(row)
        self._set_row_number(row)
        stock_code_item = self._ensure_table_item(row, self.COL_STOCK_CODE, editable=False)
        stock_code_item.setText(str(stock.get("stock_code") or ""))
        stock_code_item.setData(Qt.UserRole, int(stock.get("stock_id") or 0))
        stock_code_item.setData(Qt.UserRole + 1, int(stock.get("stock_id") or 0))
        stock_code_item.setData(Qt.UserRole + 2, float(stock.get("purchase_price_default") or 0))
        stock_code_item.setData(Qt.UserRole + 3, float(stock.get("sales_price") or 0))
        stock_code_item.setData(Qt.UserRole + 4, float(stock.get("vat_rate") or 0))

        product_item = self._ensure_table_item(row, self.COL_PRODUCT, editable=False)
        product_item.setText(str(stock.get("product_name") or ""))

        qty_item = self._ensure_table_item(row, self.COL_QTY, editable=True)
        if not qty_item.text().strip():
            qty_item.setText("1")

        unit_item = self._ensure_table_item(row, self.COL_UNIT, editable=False)
        unit_item.setText(str(stock.get("unit") or ""))

        unit_price_item = self._ensure_table_item(row, self.COL_UNIT_PRICE, editable=True)
        purchase_price = float(stock.get("purchase_price_default") or 0)
        sale_price = float(stock.get("sales_price") or 0)
        default_price = purchase_price if purchase_price > 0 else sale_price
        unit_price_item.setText(f"{default_price:.2f}")

        discount_item = self._ensure_table_item(row, self.COL_DISCOUNT, editable=True)
        discount_item.setText("0")
        vat_item = self._ensure_table_item(row, self.COL_VAT, editable=True)
        vat_item.setText(f"{float(stock.get('vat_rate') or 0):.2f}".rstrip("0").rstrip("."))
        self._ensure_table_item(row, self.COL_LINE_TOTAL, editable=False)
        self._recalculate_row(row)
        self._sync_table_height()

    def _ensure_row_items(self, row: int):
        for col in range(self.product_table.columnCount()):
            item = self.product_table.item(row, col)
            if item is None:
                item = QTableWidgetItem("")
                self.product_table.setItem(row, col, item)
            if col == self.COL_ROW_NO:
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                item.setTextAlignment(Qt.AlignCenter)
            elif col in (self.COL_STOCK_CODE, self.COL_PRODUCT, self.COL_UNIT, self.COL_LINE_TOTAL):
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                if col == self.COL_LINE_TOTAL:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            else:
                item.setFlags(item.flags() | Qt.ItemIsEditable)

    def _set_row_number(self, row: int):
        item = self.product_table.item(row, self.COL_ROW_NO)
        if item is None:
            item = QTableWidgetItem()
            self.product_table.setItem(row, self.COL_ROW_NO, item)
        item.setText(str(row + 1))
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        item.setTextAlignment(Qt.AlignCenter)

    def _add_product_row(self, insert_at: Optional[int] = None) -> int:
        row = self.product_table.rowCount() if insert_at is None else max(0, min(insert_at, self.product_table.rowCount()))
        self.product_table.insertRow(row)
        self._ensure_row_items(row)
        self._set_row_number(row)

        stock_item = self._ensure_table_item(row, self.COL_STOCK_CODE, editable=False)
        stock_item.setData(Qt.UserRole, 0)
        stock_item.setData(Qt.UserRole + 1, 0)
        self._ensure_table_item(row, self.COL_PRODUCT, editable=False).setText("")
        self._ensure_table_item(row, self.COL_QTY, editable=True).setText("")
        self._ensure_table_item(row, self.COL_UNIT, editable=False).setText("")
        self._ensure_table_item(row, self.COL_UNIT_PRICE, editable=True).setText("")
        self._ensure_table_item(row, self.COL_DISCOUNT, editable=True).setText("")
        self._ensure_table_item(row, self.COL_VAT, editable=True).setText("")
        self._ensure_table_item(row, self.COL_LINE_TOTAL, editable=False).setText("0.00")
        self._refresh_row_numbers()
        self._sync_table_height()
        self._update_totals()
        return row

    def _sync_table_height(self):
        self.product_table.setMinimumHeight(0)

    def _refresh_row_numbers(self):
        for row in range(self.product_table.rowCount()):
            self._set_row_number(row)

    def _focus_grid_cell(self, row: int, col: int):
        if row < 0 or row >= self.product_table.rowCount():
            return
        self.product_table.setCurrentCell(row, col)
        item = self.product_table.item(row, col)
        if item is not None:
            self.product_table.scrollToItem(item, QAbstractItemView.PositionAtCenter)
            if item.flags() & Qt.ItemIsEditable:
                self.product_table.editItem(item)

    def _advance_grid_from_cell(self, row: int, col: int):
        if col == self.COL_QTY:
            self._focus_grid_cell(row, self.COL_UNIT_PRICE)
        elif col == self.COL_UNIT_PRICE:
            self._focus_grid_cell(row, self.COL_DISCOUNT)
        elif col == self.COL_DISCOUNT:
            self._focus_grid_cell(row, self.COL_VAT)
        elif col == self.COL_VAT:
            next_row = row + 1
            if next_row >= self.product_table.rowCount():
                next_row = self._add_product_row()
            self._focus_grid_cell(next_row, self.COL_QTY)

    def _handle_editor_enter(self):
        row = self.product_table.currentRow()
        col = self.product_table.currentColumn()
        if row >= 0 and col >= 0:
            self._advance_grid_from_cell(row, col)

    def _handle_grid_key_press(self, event) -> bool:
        if event.key() == Qt.Key_Insert:
            row = self.product_table.currentRow()
            insert_at = self.product_table.rowCount() if row < 0 else row + 1
            new_row = self._add_product_row(insert_at)
            self._focus_grid_cell(new_row, self.COL_QTY)
            return True
        if event.key() == Qt.Key_Delete:
            self._remove_selected_product_row()
            return True
        if event.key() == Qt.Key_Down:
            row = self.product_table.currentRow()
            if row >= 0 and row == self.product_table.rowCount() - 1:
                new_row = self._add_product_row()
                self._focus_grid_cell(new_row, self.COL_QTY)
                return True
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            row = self.product_table.currentRow()
            col = self.product_table.currentColumn()
            if row >= 0 and col in (self.COL_STOCK_CODE, self.COL_PRODUCT):
                self._selected_stock_row = row
                self._open_stock_lookup()
                return True
            self._handle_editor_enter()
            return True
        if event.key() == Qt.Key_F5:
            self._on_save()
            return True
        if event.key() == Qt.Key_Escape:
            self.reject()
            return True
        return False

    def _ensure_table_item(self, row: int, col: int, editable: bool) -> QTableWidgetItem:
        item = self.product_table.item(row, col)
        if item is None:
            item = QTableWidgetItem("")
            self.product_table.setItem(row, col, item)
        if editable:
            item.setFlags(item.flags() | Qt.ItemIsEditable)
        else:
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        return item

    def _remove_selected_product_row(self):
        row = self.product_table.currentRow()
        if row < 0:
            return
        self.product_table.removeRow(row)
        self._selected_stock_row = None
        self._refresh_row_numbers()
        self._sync_table_height()
        self._update_totals()

    def _append_item_row(
        self,
        goods_receipt_item_id: int,
        stock_id: int,
        stock_code: str,
        product_name: str,
        qty: float,
        unit: str,
        unit_price: float,
        discount: float,
        vat: float,
    ):
        row = self._add_product_row()

        self._ensure_row_items(row)
        self._set_row_number(row)

        stock_code_item = self._ensure_table_item(row, self.COL_STOCK_CODE, editable=False)
        stock_code_item.setText(stock_code)
        stock_code_item.setData(Qt.UserRole, goods_receipt_item_id)
        stock_code_item.setData(Qt.UserRole + 1, stock_id)

        self._ensure_table_item(row, self.COL_PRODUCT, editable=False).setText(product_name)
        qty_item = self._ensure_table_item(row, self.COL_QTY, editable=True)
        qty_item.setText(f"{qty:.3f}".rstrip("0").rstrip("."))
        qty_item.setData(Qt.UserRole, qty)
        self._ensure_table_item(row, self.COL_UNIT, editable=False).setText(unit)
        self._ensure_table_item(row, self.COL_UNIT_PRICE, editable=True).setText(f"{unit_price:.2f}")
        self._ensure_table_item(row, self.COL_DISCOUNT, editable=True).setText(f"{discount:.2f}".rstrip("0").rstrip("."))
        self._ensure_table_item(row, self.COL_VAT, editable=True).setText(f"{vat:.2f}".rstrip("0").rstrip("."))
        self._ensure_table_item(row, self.COL_LINE_TOTAL, editable=False).setText("0.00")

        self._recalculate_row(row)

    def _on_product_cell_double_clicked(self, row: int, col: int):
        if col in (self.COL_STOCK_CODE, self.COL_PRODUCT):
            self._selected_stock_row = row
            self._open_stock_lookup()

    def _edit_current_cell(self):
        if self.focusWidget() is not self.product_table:
            self.product_table.setFocus()
        row = self.product_table.currentRow()
        col = self.product_table.currentColumn()
        if row < 0:
            row = 0
            if self.product_table.rowCount() == 0:
                row = self._add_product_row()
            col = self.COL_QTY
        item = self.product_table.item(row, max(col, self.COL_QTY))
        if item is not None and item.flags() & Qt.ItemIsEditable:
            self.product_table.editItem(item)

    def _on_print_shortcut(self):
        QMessageBox.information(self, "Bilgi", "Yazdırma bu ekranda henüz aktif değil.")

    def _on_whatsapp_shortcut(self):
        QMessageBox.information(self, "Bilgi", "WhatsApp paylaşımı bu ekranda henüz aktif değil.")

    def _on_product_item_changed(self, item: QTableWidgetItem):
        if item is None:
            return

        if item.column() == self.COL_ROW_NO:
            return

        self._selected_stock_row = item.row()
        row = item.row()
        if item.column() == self.COL_QTY:
            max_qty = float(item.data(Qt.UserRole) or self._cell_float(row, self.COL_QTY, 0))
            qty = self._cell_float(row, self.COL_QTY, 0)
            if qty < 0:
                qty = 0
            if qty > max_qty:
                qty = max_qty
            self.product_table.blockSignals(True)
            item.setText(f"{qty:.3f}".rstrip("0").rstrip("."))
            self.product_table.blockSignals(False)

        self._recalculate_row(row)
        self._update_totals()

    def _validate_before_save(self) -> Optional[str]:
        invoice_number = self.invoice_number_input.text().strip()
        if not invoice_number:
            return "Fatura No boş olamaz."

        if not self.cari_input.text().strip():
            return "Cari seçimi zorunludur."

        has_stock_line = False
        for row in range(self.product_table.rowCount()):
            stock_code_item = self.product_table.item(row, self.COL_STOCK_CODE)
            qty = self._cell_float(row, self.COL_QTY, 0)
            if stock_code_item is None or not stock_code_item.text().strip():
                continue
            if qty <= 0:
                return f"{row + 1}. satırdaki miktar 0'dan büyük olmalıdır."
            has_stock_line = True

        if not has_stock_line:
            return "En az bir stok satırı girilmelidir."

        existing = PurchaseInvoiceModel.invoice_detail(invoice_number)
        if existing is not None and not (self.is_edit_mode and invoice_number == self.invoice_number):
            return "Bu fatura numarası zaten kullanılıyor."

        return None

    def _cell_float(self, row: int, col: int, default: float) -> float:
        item = self.product_table.item(row, col)
        if item is None:
            return default
        try:
            return float(item.text().strip() or default)
        except ValueError:
            return default

    def _recalculate_row(self, row: int):
        qty = self._cell_float(row, self.COL_QTY, 0)
        unit_price = self._cell_float(row, self.COL_UNIT_PRICE, 0)
        discount_percent = self._cell_float(row, self.COL_DISCOUNT, 0)
        vat_percent = self._cell_float(row, self.COL_VAT, 0)

        base = qty * unit_price
        discount_amount = base * (discount_percent / 100.0)
        net = base - discount_amount
        vat_amount = net * (vat_percent / 100.0)
        line_total = net + vat_amount

        self.product_table.blockSignals(True)
        line_item = self.product_table.item(row, self.COL_LINE_TOTAL)
        if line_item is None:
            line_item = QTableWidgetItem()
            line_item.setFlags(line_item.flags() & ~Qt.ItemIsEditable)
            line_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.product_table.setItem(row, self.COL_LINE_TOTAL, line_item)
        line_item.setText(f"{line_total:.2f}")
        self.product_table.blockSignals(False)

    def _update_totals(self):
        subtotal = 0.0
        discount = 0.0
        vat = 0.0

        for row in range(self.product_table.rowCount()):
            qty = self._cell_float(row, self.COL_QTY, 0)
            unit_price = self._cell_float(row, self.COL_UNIT_PRICE, 0)
            discount_percent = self._cell_float(row, self.COL_DISCOUNT, 0)
            vat_percent = self._cell_float(row, self.COL_VAT, 0)

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

    def _load_invoice(self, invoice_number: str):
        invoice = PurchaseInvoiceModel.invoice_detail(invoice_number)
        if invoice is None:
            QMessageBox.warning(self, "Uyarı", "Alış faturası bulunamadı.")
            self.reject()
            return

        availability_map: Dict[int, float] = {}
        goods_receipt_id = int(invoice.get("goods_receipt_id") or 0)
        if goods_receipt_id > 0:
            for receipt_item in PurchaseInvoiceModel.goods_receipt_items_for_invoice(goods_receipt_id):
                key = int(receipt_item.get("goods_receipt_item_id") or 0)
                availability_map[key] = float(receipt_item.get("remaining_qty") or 0)

        self.invoice_number_input.setText(str(invoice.get("invoice_number") or ""))
        supplier_record = self._supplier_record_by_id(int(invoice.get("supplier_id") or 0))
        if supplier_record is None:
            supplier_record = {
                "supplier_id": int(invoice.get("supplier_id") or 0),
                "cari_kodu": "",
                "firma_unvani": str(invoice.get("supplier_name") or ""),
                "payment_term": "",
                "default_currency": str(invoice.get("currency") or "USD"),
            }
        self._apply_cari_record(supplier_record)
        self.purchase_order_input.setText(str(invoice.get("purchase_order_number") or ""))

        invoice_date = QDate.fromString(str(invoice.get("invoice_date") or ""), "yyyy-MM-dd")
        if invoice_date.isValid():
            self.invoice_date_input.setDate(invoice_date)

        due_date = QDate.fromString(str(invoice.get("due_date") or ""), "yyyy-MM-dd")
        if due_date.isValid():
            self.due_date_input.setDate(due_date)

        self.currency_combo.setCurrentText(str(invoice.get("currency") or "USD"))
        self.exchange_rate_input.setValue(float(invoice.get("exchange_rate") or 1.0))
        self.notes_input.setPlainText(str(invoice.get("notes") or ""))

        self.product_table.blockSignals(True)
        self.product_table.setRowCount(0)
        for item in invoice.get("items", []):
            invoice_qty = float(item.get("quantity") or 0)
            gr_item_id = int(item.get("goods_receipt_item_id") or 0)
            self._append_item_row(
                goods_receipt_item_id=gr_item_id,
                stock_id=int(item.get("stock_id") or 0),
                stock_code=str(item.get("stock_code") or ""),
                product_name=str(item.get("product_name") or ""),
                qty=invoice_qty,
                unit=str(item.get("unit") or ""),
                unit_price=float(item.get("unit_price") or 0),
                discount=float(item.get("discount_percent") or 0),
                vat=float(item.get("vat_percent") or 0),
            )
            row = self.product_table.rowCount() - 1
            qty_item = self.product_table.item(row, self.COL_QTY)
            if qty_item is not None:
                max_qty = invoice_qty + float(availability_map.get(gr_item_id, 0))
                qty_item.setData(Qt.UserRole, max_qty)
        self.product_table.blockSignals(False)
        if self.product_table.rowCount() == 0:
            self._add_product_row()
        self._sync_table_height()
        self._update_totals()

    def _on_save(self):
        validation_error = self._validate_before_save()
        if validation_error:
            QMessageBox.warning(self, "Uyarı", validation_error)
            return

        entered_invoice_number = self.invoice_number_input.text().strip()

        supplier_id = int(self._selected_cari_record.get("supplier_id") or 0) if self._selected_cari_record else 0
        supplier_id = PurchaseInvoiceModel.resolve_or_create_supplier_id(
            supplier_id=supplier_id,
            cari_kodu=str(self.cari_kodu_input.text().strip()),
            firma_unvani=str(self.company_name_input.text().strip() or self.cari_input.text().strip()),
            default_currency=str(self.currency_combo.currentText().strip() or "USD"),
            payment_term=str(self.payment_term_input.text().strip()) if hasattr(self, "payment_term_input") else "",
            yetkili="",
        )
        if supplier_id <= 0:
            QMessageBox.warning(self, "Uyarı", "Cari bilgisi geçerli değil.")
            return

        purchase_order_id = 0
        if self.is_edit_mode:
            existing = PurchaseInvoiceModel.invoice_detail(self.invoice_number or entered_invoice_number)
            if existing is not None:
                purchase_order_id = int(existing.get("purchase_order_id") or 0)

        items: List[Dict[str, Any]] = []
        for row in range(self.product_table.rowCount()):
            stock_code_item = self.product_table.item(row, self.COL_STOCK_CODE)
            if stock_code_item is None or not stock_code_item.text().strip():
                continue
            qty = self._cell_float(row, self.COL_QTY, 0)
            if qty <= 0:
                continue

            items.append(
                {
                    "goods_receipt_item_id": 0,
                    "stock_id": int(stock_code_item.data(Qt.UserRole + 1) or 0),
                    "quantity": qty,
                    "unit": self.product_table.item(row, self.COL_UNIT).text().strip() if self.product_table.item(row, self.COL_UNIT) else "",
                    "unit_price": self._cell_float(row, self.COL_UNIT_PRICE, 0),
                    "discount_percent": self._cell_float(row, self.COL_DISCOUNT, 0),
                    "vat_percent": self._cell_float(row, self.COL_VAT, 0),
                }
            )

        if not items:
            QMessageBox.warning(self, "Uyarı", "En az bir stok satırı girilmelidir.")
            return

        created_by = os.getenv("USERNAME") or os.getenv("USER") or "SYSTEM"

        try:
            PurchaseInvoiceModel.save_invoice(
                invoice_number=entered_invoice_number,
                supplier_id=supplier_id,
                purchase_order_id=purchase_order_id,
                goods_receipt_id=0,
                invoice_date=self.invoice_date_input.date().toString("yyyy-MM-dd"),
                due_date=self.due_date_input.date().toString("yyyy-MM-dd"),
                currency=self.currency_combo.currentText(),
                exchange_rate=float(self.exchange_rate_input.value()),
                notes=self.notes_input.toPlainText().strip(),
                items=items,
                created_by=created_by,
                existing_invoice_number=self.invoice_number if self.is_edit_mode else None,
            )
            self.saved_invoice_number = self.invoice_number_input.text().strip()
            self.accept()
        except Exception as exc:
            QMessageBox.critical(self, "Hata", f"Alış faturası kaydedilemedi:\n{exc}")

    def get_saved_invoice_number(self) -> Optional[str]:
        return self.saved_invoice_number or None

    def showEvent(self, event):  # noqa: N802
        super().showEvent(event)
        if hasattr(self, "scroll_area") and self.scroll_area is not None:
            content_widget = self.scroll_area.widget()
            if content_widget is not None:
                content_widget.adjustSize()
            self.scroll_area.verticalScrollBar().setValue(0)

    def eventFilter(self, watched, event):  # noqa: N802
        if watched is self.cari_input and event.type() == QEvent.MouseButtonDblClick:
            self._open_cari_lookup()
            return True

        if event.type() == QEvent.Wheel and hasattr(self, "scroll_area") and self.scroll_area is not None:
            if watched is not self.scroll_area.verticalScrollBar() and isinstance(watched, QWidget) and self.isAncestorOf(watched):
                delta = event.angleDelta().y()
                step = self.scroll_area.verticalScrollBar().singleStep() * 3
                if delta > 0:
                    self.scroll_area.verticalScrollBar().setValue(self.scroll_area.verticalScrollBar().value() - step)
                elif delta < 0:
                    self.scroll_area.verticalScrollBar().setValue(self.scroll_area.verticalScrollBar().value() + step)
                return True

        if watched in getattr(self, "_focus_targets", []):
            if event.type() == QEvent.FocusIn:
                effect = QGraphicsDropShadowEffect(watched)
                effect.setBlurRadius(26)
                effect.setOffset(0, 0)
                effect.setColor(QColor("#f97316"))
                watched.setGraphicsEffect(effect)
            elif event.type() == QEvent.FocusOut:
                watched.setGraphicsEffect(None)
        return super().eventFilter(watched, event)
