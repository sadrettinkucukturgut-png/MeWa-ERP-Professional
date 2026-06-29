import os
from typing import Any, Dict, List, Optional

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
)

from models.packing_list_model import PackingListModel
from services.document_preview_engine import DocumentLineItem, DocumentPreviewWindow, DocumentTemplate


class MoveToPalletDialog(QDialog):
    def __init__(self, stock_code: str, pallets: List[str], current_pallet: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Ürünü Palete Taşı")
        self.selected_pallet = ""

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"Ürünü taşı: {stock_code}"))
        layout.addWidget(QLabel("Hedef palet"))

        self.pallet_combo = QComboBox()
        self.pallet_combo.addItems(pallets)
        if current_pallet in pallets:
            self.pallet_combo.setCurrentText(current_pallet)
        layout.addWidget(self.pallet_combo)

        buttons = QHBoxLayout()
        buttons.addStretch()
        move_button = QPushButton("Taşı")
        cancel_button = QPushButton("İptal")
        move_button.clicked.connect(self._accept)
        cancel_button.clicked.connect(self.reject)
        buttons.addWidget(move_button)
        buttons.addWidget(cancel_button)
        layout.addLayout(buttons)

        self.setStyleSheet(
            "QDialog{background:#0b1220;} QLabel{color:#e2e8f0;}"
            "QComboBox{background:#0f172a; color:#e2e8f0; border:1px solid #334155; border-radius:8px; padding:6px;}"
            "QPushButton{background:#1e293b; color:#f8fafc; border:1px solid #334155; border-radius:8px; padding:8px 12px;}"
            "QPushButton:hover{background:#334155;}"
        )

    def _accept(self):
        self.selected_pallet = self.pallet_combo.currentText().strip()
        self.accept()


class NewPackingListDialog(QDialog):
    COL_ROW = 0
    COL_PALLET = 1
    COL_STOCK_CODE = 2
    COL_DESCRIPTION = 3
    COL_UNIT_WEIGHT = 4
    COL_HS = 5
    COL_QTY = 6
    COL_UNIT = 7
    COL_NET = 8
    COL_GROSS = 9
    COL_REMARKS = 10

    DEFAULT_PALLET = "Palet 1"
    VIEW_ALL = "Tümü"

    def __init__(
        self,
        source_type: Optional[str] = None,
        source_number: Optional[str] = None,
        packing_list_number: Optional[str] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Packing List")
        self.resize(1460, 820)
        self.setMinimumSize(1200, 720)

        self.source_type = str(source_type or "").strip()
        self.source_number = str(source_number or "").strip()
        self.existing_packing_list_number = str(packing_list_number or "").strip()
        self.is_edit_mode = bool(self.existing_packing_list_number)

        self._pallet_order: List[str] = []
        self._pallet_weights: Dict[str, float] = {}

        self._build_ui()

        if self.is_edit_mode:
            self._load_existing(self.existing_packing_list_number)
        else:
            self.packing_list_number_input.setText(PackingListModel.packing_list_number_generate())
            self.packing_date_input.setDate(QDate.currentDate())
            self._ensure_pallet(self.DEFAULT_PALLET)
            if self.source_type and self.source_number:
                self._import_from_source(self.source_type, self.source_number)

        self._refresh_row_numbers()
        self._refresh_pallet_controls()
        self._recalculate_all()
        self._update_action_states()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        title = QLabel("Packing List")
        title.setStyleSheet("font-size:16px; font-weight:700; color:#f8fafc;")
        root.addWidget(title)

        form_frame = QFrame()
        form_frame.setStyleSheet("QFrame{background:#0f172a; border:1px solid #334155; border-radius:10px;}")
        form_layout = QGridLayout(form_frame)
        form_layout.setContentsMargins(10, 8, 10, 8)
        form_layout.setHorizontalSpacing(10)
        form_layout.setVerticalSpacing(6)

        self.packing_list_number_input = QLineEdit()
        self.packing_date_input = QDateEdit()
        self.packing_date_input.setCalendarPopup(True)
        self.customer_input = QLineEdit()
        self.customer_input.setReadOnly(True)
        self.customer_code_input = QLineEdit()
        self.customer_code_input.setReadOnly(True)
        self.consignee_input = QLineEdit()
        self.notify_party_input = QLineEdit()
        self.invoice_number_input = QLineEdit()
        self.proforma_number_input = QLineEdit()

        self.container_no_input = QLineEdit()
        self.seal_no_input = QLineEdit()
        self.country_input = QLineEdit()
        self.port_loading_input = QLineEdit()
        self.port_discharge_input = QLineEdit()
        self.delivery_terms_input = QLineEdit()
        self.payment_terms_input = QLineEdit()
        self.estimated_delivery_input = QLineEdit()
        self.currency_combo = QComboBox()
        self.currency_combo.addItems(["USD", "EUR", "TRY", "AED", "SAR", "GBP", "CNY", "RUB"])
        self.notes_input = QTextEdit()
        self.notes_input.setFixedHeight(42)

        compact_fields = [
            ("Packing List No", self.packing_list_number_input),
            ("Tarih", self.packing_date_input),
            ("Müşteri", self.customer_input),
            ("Müşteri Kodu", self.customer_code_input),
            ("Fatura No", self.invoice_number_input),
            ("Proforma No", self.proforma_number_input),
            ("Consignee", self.consignee_input),
            ("Notify Party", self.notify_party_input),
            ("Konteyner No", self.container_no_input),
            ("Mühür No", self.seal_no_input),
            ("Yükleme Limanı", self.port_loading_input),
            ("Varış Limanı", self.port_discharge_input),
            ("Ülke", self.country_input),
            ("Teslim Şartları", self.delivery_terms_input),
            ("Ödeme Şartları", self.payment_terms_input),
            ("Tahmini Teslim", self.estimated_delivery_input),
            ("Para Birimi", self.currency_combo),
            ("Notlar", self.notes_input),
        ]

        for index, (label_text, widget) in enumerate(compact_fields):
            row = index // 4
            col = (index % 4) * 2
            label = QLabel(label_text)
            label.setMinimumWidth(92)
            form_layout.addWidget(label, row, col)
            form_layout.addWidget(widget, row, col + 1)
        root.addWidget(form_frame)

        pallet_frame = QFrame()
        pallet_frame.setStyleSheet("QFrame{background:#0f172a; border:1px solid #334155; border-radius:10px;}")
        pallet_layout = QVBoxLayout(pallet_frame)
        pallet_layout.setContentsMargins(10, 8, 10, 8)
        pallet_layout.setSpacing(6)

        selector_row = QHBoxLayout()
        self.manage_pallet_selector = QComboBox()
        self.manage_pallet_selector.currentIndexChanged.connect(self._on_manage_pallet_changed)

        self.view_pallet_selector = QComboBox()
        self.view_pallet_selector.currentIndexChanged.connect(self._on_view_pallet_changed)

        self.pallet_weight_input = QDoubleSpinBox()
        self.pallet_weight_input.setDecimals(3)
        self.pallet_weight_input.setMinimum(0)
        self.pallet_weight_input.setMaximum(999999)
        self.pallet_weight_input.valueChanged.connect(self._on_pallet_weight_changed)

        selector_row.addWidget(QLabel("Palet"))
        selector_row.addWidget(self.manage_pallet_selector, 1)
        selector_row.addSpacing(8)
        selector_row.addWidget(QLabel("Görüntü"))
        selector_row.addWidget(self.view_pallet_selector, 1)
        selector_row.addSpacing(8)
        selector_row.addWidget(QLabel("Palet Ağırlığı"))
        selector_row.addWidget(self.pallet_weight_input)
        pallet_layout.addLayout(selector_row)

        button_row = QHBoxLayout()
        self.btn_new_pallet = QPushButton("Yeni Palet")
        self.btn_rename_pallet = QPushButton("Palet Adını Değiştir")
        self.btn_delete_pallet = QPushButton("Boş Paleti Sil")
        self.btn_move_item = QPushButton("Seçili Ürünü Palete Taşı")
        self.btn_split = QPushButton("Paleti Böl")
        self.btn_merge = QPushButton("Paletleri Birleştir")

        self.btn_new_pallet.clicked.connect(self._new_pallet)
        self.btn_rename_pallet.clicked.connect(self._rename_pallet)
        self.btn_delete_pallet.clicked.connect(self._delete_empty_pallet)
        self.btn_move_item.clicked.connect(self._move_selected_item)
        self.btn_split.clicked.connect(self._split_selected_item)
        self.btn_merge.clicked.connect(self._merge_current_pallet)

        for button in (
            self.btn_new_pallet,
            self.btn_rename_pallet,
            self.btn_delete_pallet,
            self.btn_move_item,
            self.btn_split,
            self.btn_merge,
        ):
            button_row.addWidget(button)
        pallet_layout.addLayout(button_row)
        root.addWidget(pallet_frame)

        self.table = QTableWidget()
        self.table.setColumnCount(11)
        self.table.setHorizontalHeaderLabels(
            [
                "#",
                "PALLET",
                "Stok Kodu",
                "Açıklama",
                "Quantity Weight",
                "HS Kod",
                "Miktar",
                "Birim",
                "Net Weight",
                "Gross Weight",
                "Not",
            ]
        )
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setWordWrap(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.itemChanged.connect(self._on_item_changed)
        self.table.itemSelectionChanged.connect(self._update_action_states)
        self.table.verticalHeader().setDefaultSectionSize(42)
        self.table.setColumnWidth(self.COL_ROW, 44)
        self.table.setColumnWidth(self.COL_PALLET, 110)
        self.table.setColumnWidth(self.COL_STOCK_CODE, 120)
        self.table.setColumnWidth(self.COL_DESCRIPTION, 300)
        self.table.setColumnWidth(self.COL_UNIT_WEIGHT, 110)
        self.table.setColumnWidth(self.COL_HS, 95)
        self.table.setColumnWidth(self.COL_QTY, 90)
        self.table.setColumnWidth(self.COL_UNIT, 80)
        self.table.setColumnWidth(self.COL_NET, 120)
        self.table.setColumnWidth(self.COL_GROSS, 120)
        self.table.setColumnWidth(self.COL_REMARKS, 220)
        self.table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        root.addWidget(self.table, 1)

        footer_row = QHBoxLayout()
        footer_row.setSpacing(10)

        summary = QFrame()
        summary.setStyleSheet("QFrame{background:#0f172a; border:1px solid #334155; border-radius:10px;}")
        summary_layout = QGridLayout(summary)
        summary_layout.setContentsMargins(10, 8, 10, 8)
        summary_layout.setHorizontalSpacing(14)
        summary_layout.setVerticalSpacing(6)
        self.sum_pallets = QLabel("0")
        self.sum_pieces = QLabel("0 PCS")
        self.sum_net = QLabel("0.00 KG")
        self.sum_gross = QLabel("0.00 KG")

        summary_fields = [
            ("Toplam Palet", self.sum_pallets),
            ("Toplam Parça", self.sum_pieces),
            ("Toplam Net Ağırlık", self.sum_net),
            ("Toplam Brüt Ağırlık", self.sum_gross),
        ]
        for i, (label_text, value_label) in enumerate(summary_fields):
            summary_layout.addWidget(QLabel(label_text), i, 0)
            summary_layout.addWidget(value_label, i, 1)
            value_label.setStyleSheet("font-size:14px; font-weight:700; color:#f8fafc;")
        footer_row.addWidget(summary, 0)

        actions = QHBoxLayout()
        self.btn_preview = QPushButton("Önizleme")
        self.btn_save = QPushButton("Kaydet")
        self.btn_save_close = QPushButton("Kaydet ve Kapat")
        self.btn_cancel = QPushButton("İptal")
        self.btn_preview.clicked.connect(self._on_preview)
        self.btn_save.clicked.connect(self._on_save)
        self.btn_save_close.clicked.connect(self._on_save_close)
        self.btn_cancel.clicked.connect(self.reject)
        actions.addStretch()
        actions.addWidget(self.btn_preview)
        actions.addWidget(self.btn_save)
        actions.addWidget(self.btn_save_close)
        actions.addWidget(self.btn_cancel)

        actions_frame = QFrame()
        actions_frame.setStyleSheet("QFrame{background:#0f172a; border:1px solid #334155; border-radius:10px;}")
        actions_frame.setLayout(actions)
        footer_row.addWidget(actions_frame, 1)
        root.addLayout(footer_row)

        self.setStyleSheet(
            "QDialog{background:#0b1220;} QLabel{color:#e2e8f0;}"
            "QLineEdit,QComboBox,QDateEdit,QTextEdit,QDoubleSpinBox{background:#0f172a; color:#e2e8f0; border:1px solid #334155; border-radius:8px; padding:6px;}"
            "QPushButton{background:#1e293b; color:#f8fafc; border:1px solid #334155; border-radius:8px; padding:8px 12px;}"
            "QPushButton:hover{background:#334155;}"
            "QTableWidget{background:#111827; alternate-background-color:#0f172a; color:#e5e7eb; border:1px solid #334155;}"
            "QHeaderView::section{background:#1f2937; color:#e5e7eb; padding:8px 6px;}"
        )

    def _ensure_pallet(self, pallet_no: str, pallet_weight: float = 25.0):
        pallet = str(pallet_no or "").strip()
        if not pallet:
            return
        if pallet not in self._pallet_order:
            self._pallet_order.append(pallet)
        self._pallet_weights.setdefault(pallet, float(pallet_weight))

    def _next_pallet_name(self) -> str:
        index = 1
        while f"Palet {index}" in self._pallet_order:
            index += 1
        return f"Palet {index}"

    def _cell_text(self, row: int, col: int) -> str:
        item = self.table.item(row, col)
        return "" if item is None else item.text().strip()

    def _cell_float(self, row: int, col: int) -> float:
        try:
            text = self._cell_text(row, col).replace("KG", "").replace("PCS", "").strip()
            return float(text or 0)
        except ValueError:
            return 0.0

    def _format_weight(self, value: float) -> str:
        return f"{value:.2f} KG"

    def _set_aligned_text(self, row: int, col: int, text: str, alignment: Qt.AlignmentFlag, editable: bool = False):
        item = self._ensure_item(row, col, editable=editable)
        item.setText(text)
        item.setTextAlignment(alignment)
        return item

    def _ensure_item(self, row: int, col: int, editable: bool = True) -> QTableWidgetItem:
        item = self.table.item(row, col)
        if item is None:
            item = QTableWidgetItem("")
            self.table.setItem(row, col, item)
        if editable:
            item.setFlags(item.flags() | Qt.ItemIsEditable)
        else:
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        return item

    def _set_row(self, row: int, source: Dict[str, Any], pallet_no: str):
        stock_id = int(source.get("stock_id") or 0)
        stock_code = str(source.get("stock_code") or "")
        description = str(source.get("description") or source.get("product_name") or "")
        hs_code = str(source.get("hs_code") or "")
        quantity = float(source.get("quantity") or 0)
        unit = str(source.get("unit") or "")
        product_weight = float(source.get("product_weight") or source.get("weight") or 0)
        remarks = str(source.get("remarks") or "")

        self.table.blockSignals(True)
        self._ensure_item(row, self.COL_ROW, editable=False)
        self._ensure_item(row, self.COL_PALLET, editable=False).setText(pallet_no)
        self.table.item(row, self.COL_PALLET).setTextAlignment(Qt.AlignCenter)

        stock_item = self._ensure_item(row, self.COL_STOCK_CODE, editable=False)
        stock_item.setText(stock_code)
        stock_item.setData(Qt.UserRole + 1, stock_id)
        stock_item.setData(Qt.UserRole + 2, product_weight)

        self._ensure_item(row, self.COL_DESCRIPTION, editable=False).setText(description)
        self._ensure_item(row, self.COL_DESCRIPTION, editable=False).setToolTip(description)
        self._set_aligned_text(row, self.COL_UNIT_WEIGHT, self._format_weight(product_weight), Qt.AlignRight | Qt.AlignVCenter, editable=False)
        self._ensure_item(row, self.COL_HS, editable=False).setText(hs_code)
        self._set_aligned_text(row, self.COL_QTY, f"{quantity:.3f}".rstrip("0").rstrip("."), Qt.AlignCenter, editable=True)
        self._set_aligned_text(row, self.COL_UNIT, unit, Qt.AlignCenter, editable=False)
        self._set_aligned_text(row, self.COL_NET, self._format_weight(0), Qt.AlignRight | Qt.AlignVCenter, editable=False)
        self._set_aligned_text(row, self.COL_GROSS, self._format_weight(0), Qt.AlignRight | Qt.AlignVCenter, editable=False)
        self._ensure_item(row, self.COL_REMARKS, editable=True).setText(remarks)
        self.table.blockSignals(False)

    def _refresh_row_numbers(self):
        self.table.blockSignals(True)
        for row in range(self.table.rowCount()):
            row_item = self._ensure_item(row, self.COL_ROW, editable=False)
            row_item.setText(str(row + 1))
            row_item.setTextAlignment(Qt.AlignCenter)
        self.table.blockSignals(False)

    def _current_manage_pallet(self) -> str:
        return self.manage_pallet_selector.currentText().strip()

    def _current_view_pallet(self) -> str:
        return self.view_pallet_selector.currentText().strip()

    def _visible_rows(self) -> List[int]:
        return [row for row in range(self.table.rowCount()) if not self.table.isRowHidden(row)]

    def _refresh_pallet_controls(self):
        current_manage = self._current_manage_pallet()
        current_view = self._current_view_pallet()

        self.manage_pallet_selector.blockSignals(True)
        self.manage_pallet_selector.clear()
        self.manage_pallet_selector.addItems(self._pallet_order)
        if current_manage in self._pallet_order:
            self.manage_pallet_selector.setCurrentText(current_manage)
        elif self._pallet_order:
            self.manage_pallet_selector.setCurrentIndex(0)
        self.manage_pallet_selector.blockSignals(False)

        self.view_pallet_selector.blockSignals(True)
        self.view_pallet_selector.clear()
        self.view_pallet_selector.addItem(self.VIEW_ALL)
        self.view_pallet_selector.addItems(self._pallet_order)
        if current_view == self.VIEW_ALL:
            self.view_pallet_selector.setCurrentText(self.VIEW_ALL)
        elif current_view in self._pallet_order:
            self.view_pallet_selector.setCurrentText(current_view)
        else:
            self.view_pallet_selector.setCurrentText(self.VIEW_ALL)
        self.view_pallet_selector.blockSignals(False)

        self._sync_pallet_weight_spin()
        self._apply_view_filter()
        self._update_action_states()

    def _sync_pallet_weight_spin(self):
        pallet = self._current_manage_pallet()
        self.pallet_weight_input.blockSignals(True)
        self.pallet_weight_input.setValue(float(self._pallet_weights.get(pallet, 0.0)))
        self.pallet_weight_input.blockSignals(False)

    def _apply_view_filter(self):
        selected = self._current_view_pallet()
        for row in range(self.table.rowCount()):
            pallet = self._cell_text(row, self.COL_PALLET)
            hide_row = selected not in ("", self.VIEW_ALL) and pallet != selected
            self.table.setRowHidden(row, hide_row)
        self._refresh_summary()

    def _pallet_rows(self) -> Dict[str, List[int]]:
        grouped: Dict[str, List[int]] = {}
        for row in range(self.table.rowCount()):
            pallet = self._cell_text(row, self.COL_PALLET)
            if pallet:
                grouped.setdefault(pallet, []).append(row)
        return grouped

    def _selected_row(self) -> int:
        return self.table.currentRow() if self.table.currentRow() >= 0 else -1

    def _update_action_states(self):
        row = self._selected_row()
        has_selected_product = row >= 0 and bool(self._cell_text(row, self.COL_STOCK_CODE))
        has_manage_pallet = bool(self._current_manage_pallet())
        self.btn_move_item.setEnabled(has_selected_product and bool(self._pallet_order))
        self.btn_split.setEnabled(has_selected_product)
        self.btn_rename_pallet.setEnabled(has_manage_pallet)
        self.btn_delete_pallet.setEnabled(has_manage_pallet)
        self.btn_merge.setEnabled(has_manage_pallet and len(self._pallet_order) > 1)

    def _import_from_source(self, source_type: str, source_number: str):
        detail = PackingListModel.source_detail(source_type, source_number)
        if detail is None:
            QMessageBox.warning(self, "Uyarı", "Kaynak belge bulunamadı.")
            return

        self.source_type = source_type
        self.source_number = source_number
        self.customer_input.setText(str(detail.get("customer_name") or ""))
        self.customer_input.setProperty("customer_id", int(detail.get("customer_id") or 0))
        self.customer_code_input.setText(str(detail.get("customer_code") or ""))
        self.consignee_input.setText(str(detail.get("customer_name") or ""))
        self.notify_party_input.setText(str(detail.get("customer_name") or ""))
        self.country_input.setText(str(detail.get("country") or ""))
        self.payment_terms_input.setText(str(detail.get("payment_terms") or ""))
        self.delivery_terms_input.setText(str(detail.get("delivery_terms") or ""))
        self.currency_combo.setCurrentText(str(detail.get("currency") or "USD") or "USD")
        self.notes_input.setPlainText(str(detail.get("notes") or ""))

        if source_type == "SalesInvoice":
            self.invoice_number_input.setText(source_number)
            self.proforma_number_input.setText(str(detail.get("source_proforma_number") or ""))
        else:
            self.proforma_number_input.setText(source_number)
            self.invoice_number_input.clear()

        self.table.blockSignals(True)
        self.table.setRowCount(0)
        self.table.blockSignals(False)
        self._pallet_order = []
        self._pallet_weights = {}
        self._ensure_pallet(self.DEFAULT_PALLET)

        for src_item in detail.get("items", []):
            row = self.table.rowCount()
            self.table.insertRow(row)
            self._set_row(row, src_item, self.DEFAULT_PALLET)

        self._refresh_row_numbers()
        self._refresh_pallet_controls()

    def _load_existing(self, packing_list_number: str):
        detail = PackingListModel.packing_list_detail(packing_list_number)
        if detail is None:
            QMessageBox.warning(self, "Uyarı", "Packing List bulunamadı.")
            self.reject()
            return

        self.source_type = str(detail.get("source_type") or "")
        self.source_number = str(detail.get("source_number") or "")

        self.packing_list_number_input.setText(str(detail.get("packing_list_number") or ""))
        dt = QDate.fromString(str(detail.get("packing_date") or ""), "yyyy-MM-dd")
        if dt.isValid():
            self.packing_date_input.setDate(dt)

        self.customer_input.setText(str(detail.get("customer_name") or ""))
        self.customer_input.setProperty("customer_id", int(detail.get("customer_id") or 0))
        self.customer_code_input.setText(str(detail.get("customer_code") or ""))
        self.consignee_input.setText(str(detail.get("consignee") or ""))
        self.notify_party_input.setText(str(detail.get("notify_party") or ""))
        self.invoice_number_input.setText(str(detail.get("invoice_number") or ""))
        self.proforma_number_input.setText(str(detail.get("proforma_number") or ""))
        self.container_no_input.setText(str(detail.get("container_no") or ""))
        self.seal_no_input.setText(str(detail.get("seal_no") or ""))
        self.country_input.setText(str(detail.get("country") or ""))
        self.port_loading_input.setText(str(detail.get("port_of_loading") or ""))
        self.port_discharge_input.setText(str(detail.get("port_of_discharge") or ""))
        self.delivery_terms_input.setText(str(detail.get("delivery_terms") or ""))
        self.payment_terms_input.setText(str(detail.get("payment_terms") or ""))
        self.estimated_delivery_input.setText(str(detail.get("estimated_delivery") or ""))
        self.currency_combo.setCurrentText(str(detail.get("currency") or "USD") or "USD")
        self.notes_input.setPlainText(str(detail.get("notes") or ""))

        self._pallet_order = []
        self._pallet_weights = {}
        for pallet in detail.get("pallets", []):
            self._ensure_pallet(str(pallet.get("pallet_no") or ""), float(pallet.get("pallet_weight") or 0))
        if not self._pallet_order:
            self._ensure_pallet(self.DEFAULT_PALLET)

        self.table.blockSignals(True)
        self.table.setRowCount(0)
        for item in detail.get("items", []):
            row = self.table.rowCount()
            self.table.insertRow(row)
            self._set_row(row, item, str(item.get("pallet_no") or self.DEFAULT_PALLET))
        self.table.blockSignals(False)

        self._refresh_row_numbers()
        self._refresh_pallet_controls()

    def load_duplicate_data(self, packing_list_number: str):
        detail = PackingListModel.packing_list_detail(packing_list_number)
        if detail is None:
            QMessageBox.warning(self, "Uyarı", "Kopyalanacak Packing List bulunamadı.")
            return

        self.is_edit_mode = False
        self.existing_packing_list_number = ""
        self.source_type = str(detail.get("source_type") or "")
        self.source_number = str(detail.get("source_number") or "")
        self.packing_list_number_input.setText(PackingListModel.packing_list_number_generate())
        self.packing_date_input.setDate(QDate.currentDate())

        self.customer_input.setText(str(detail.get("customer_name") or ""))
        self.customer_input.setProperty("customer_id", int(detail.get("customer_id") or 0))
        self.customer_code_input.setText(str(detail.get("customer_code") or ""))
        self.consignee_input.setText(str(detail.get("consignee") or ""))
        self.notify_party_input.setText(str(detail.get("notify_party") or ""))
        self.invoice_number_input.setText(str(detail.get("invoice_number") or ""))
        self.proforma_number_input.setText(str(detail.get("proforma_number") or ""))
        self.container_no_input.setText(str(detail.get("container_no") or ""))
        self.seal_no_input.setText(str(detail.get("seal_no") or ""))
        self.country_input.setText(str(detail.get("country") or ""))
        self.port_loading_input.setText(str(detail.get("port_of_loading") or ""))
        self.port_discharge_input.setText(str(detail.get("port_of_discharge") or ""))
        self.delivery_terms_input.setText(str(detail.get("delivery_terms") or ""))
        self.payment_terms_input.setText(str(detail.get("payment_terms") or ""))
        self.estimated_delivery_input.setText(str(detail.get("estimated_delivery") or ""))
        self.currency_combo.setCurrentText(str(detail.get("currency") or "USD") or "USD")
        self.notes_input.setPlainText(str(detail.get("notes") or ""))

        self._pallet_order = []
        self._pallet_weights = {}
        for pallet in detail.get("pallets", []):
            self._ensure_pallet(str(pallet.get("pallet_no") or ""), float(pallet.get("pallet_weight") or 0))
        if not self._pallet_order:
            self._ensure_pallet(self.DEFAULT_PALLET)

        self.table.blockSignals(True)
        self.table.setRowCount(0)
        for item in detail.get("items", []):
            row = self.table.rowCount()
            self.table.insertRow(row)
            self._set_row(row, item, str(item.get("pallet_no") or self.DEFAULT_PALLET))
        self.table.blockSignals(False)
        self._refresh_row_numbers()
        self._refresh_pallet_controls()
        self._recalculate_all()

    def _on_manage_pallet_changed(self):
        self._sync_pallet_weight_spin()
        self._update_action_states()

    def _on_view_pallet_changed(self):
        self._apply_view_filter()

    def _on_pallet_weight_changed(self, value: float):
        pallet = self._current_manage_pallet()
        if not pallet:
            return
        self._pallet_weights[pallet] = float(value)
        self._recalculate_all()

    def _new_pallet(self):
        new_pallet = self._next_pallet_name()
        self._ensure_pallet(new_pallet)
        self._refresh_pallet_controls()
        self.manage_pallet_selector.setCurrentText(new_pallet)

    def _rename_pallet(self):
        current = self._current_manage_pallet()
        if not current:
            return
        new_name, ok = QInputDialog.getText(self, "Palet Adını Değiştir", "Yeni palet adı:", text=current)
        new_name = str(new_name or "").strip()
        if not ok or not new_name or new_name == current:
            return
        if new_name in self._pallet_order:
            QMessageBox.warning(self, "Uyarı", "Bu palet adı zaten var.")
            return

        self._pallet_order = [new_name if pallet == current else pallet for pallet in self._pallet_order]
        self._pallet_weights[new_name] = self._pallet_weights.pop(current, 25.0)

        self.table.blockSignals(True)
        for row in range(self.table.rowCount()):
            if self._cell_text(row, self.COL_PALLET) == current:
                self._ensure_item(row, self.COL_PALLET, editable=False).setText(new_name)
        self.table.blockSignals(False)

        self._refresh_pallet_controls()
        self.manage_pallet_selector.setCurrentText(new_name)
        self._recalculate_all()

    def _delete_empty_pallet(self):
        pallet = self._current_manage_pallet()
        if not pallet:
            return
        if any(self._cell_text(row, self.COL_PALLET) == pallet for row in range(self.table.rowCount())):
            QMessageBox.warning(self, "Uyarı", "Bu palette ürün var. Önce ürünleri taşıyın.")
            return

        self._pallet_order = [name for name in self._pallet_order if name != pallet]
        self._pallet_weights.pop(pallet, None)
        if not self._pallet_order:
            self._ensure_pallet(self.DEFAULT_PALLET)
        self._refresh_pallet_controls()
        self._recalculate_all()

    def _move_selected_item(self):
        row = self._selected_row()
        if row < 0:
            return
        dialog = MoveToPalletDialog(
            stock_code=self._cell_text(row, self.COL_STOCK_CODE),
            pallets=self._pallet_order,
            current_pallet=self._cell_text(row, self.COL_PALLET),
            parent=self,
        )
        if not dialog.exec() or not dialog.selected_pallet:
            return
        self._ensure_item(row, self.COL_PALLET, editable=False).setText(dialog.selected_pallet)
        self._refresh_pallet_controls()
        self._recalculate_all()

    def _split_selected_item(self):
        row = self._selected_row()
        if row < 0:
            return
        qty = self._cell_float(row, self.COL_QTY)
        if qty <= 1:
            QMessageBox.warning(self, "Uyarı", "Bölme için miktar 1'den büyük olmalıdır.")
            return

        split_qty, ok = QInputDialog.getDouble(self, "Paleti Böl", "Yeni palete taşınacak miktar:", qty / 2.0, 0.001, qty - 0.001, 3)
        if not ok:
            return

        new_pallet = self._next_pallet_name()
        self._ensure_pallet(new_pallet)
        remaining_qty = qty - split_qty

        stock_item = self.table.item(row, self.COL_STOCK_CODE)
        new_data = {
            "stock_id": int(stock_item.data(Qt.UserRole + 1) or 0) if stock_item else 0,
            "stock_code": self._cell_text(row, self.COL_STOCK_CODE),
            "description": self._cell_text(row, self.COL_DESCRIPTION),
            "hs_code": self._cell_text(row, self.COL_HS),
            "quantity": split_qty,
            "unit": self._cell_text(row, self.COL_UNIT),
            "product_weight": float(stock_item.data(Qt.UserRole + 2) or 0) if stock_item else 0,
            "remarks": self._cell_text(row, self.COL_REMARKS),
        }

        self.table.blockSignals(True)
        self._ensure_item(row, self.COL_QTY, editable=True).setText(f"{remaining_qty:.3f}".rstrip("0").rstrip("."))
        self.table.blockSignals(False)

        new_row = self.table.rowCount()
        self.table.insertRow(new_row)
        self._set_row(new_row, new_data, new_pallet)

        self._refresh_row_numbers()
        self._refresh_pallet_controls()
        self.manage_pallet_selector.setCurrentText(new_pallet)
        self._recalculate_all()

    def _merge_current_pallet(self):
        current = self._current_manage_pallet()
        targets = [pallet for pallet in self._pallet_order if pallet != current]
        if not current or not targets:
            return
        target, ok = QInputDialog.getItem(self, "Paletleri Birleştir", "Hedef palet:", targets, editable=False)
        if not ok:
            return

        self.table.blockSignals(True)
        for row in range(self.table.rowCount()):
            if self._cell_text(row, self.COL_PALLET) == current:
                self._ensure_item(row, self.COL_PALLET, editable=False).setText(target)
        self.table.blockSignals(False)

        self._pallet_weights[target] = self._pallet_weights.get(target, 0.0) + self._pallet_weights.get(current, 0.0)
        self._pallet_order = [name for name in self._pallet_order if name != current]
        self._pallet_weights.pop(current, None)
        self._refresh_pallet_controls()
        self.manage_pallet_selector.setCurrentText(target)
        self._recalculate_all()

    def _on_item_changed(self, item: QTableWidgetItem):
        if item is None:
            return
        if item.column() == self.COL_QTY and self._cell_float(item.row(), self.COL_QTY) < 0:
            self.table.blockSignals(True)
            item.setText("0")
            self.table.blockSignals(False)
        self._recalculate_all()

    def _recalculate_all(self):
        grouped_rows: Dict[str, List[int]] = {name: [] for name in self._pallet_order}
        for row in range(self.table.rowCount()):
            pallet = self._cell_text(row, self.COL_PALLET)
            grouped_rows.setdefault(pallet, []).append(row)

        self.table.blockSignals(True)
        for row in range(self.table.rowCount()):
            stock_item = self.table.item(row, self.COL_STOCK_CODE)
            product_weight = float(stock_item.data(Qt.UserRole + 2) if stock_item is not None else 0)
            qty = self._cell_float(row, self.COL_QTY)
            net = max(0.0, qty * product_weight)
            self._set_aligned_text(row, self.COL_UNIT_WEIGHT, self._format_weight(product_weight), Qt.AlignRight | Qt.AlignVCenter, editable=False)
            self._set_aligned_text(row, self.COL_QTY, f"{qty:.3f}".rstrip("0").rstrip("."), Qt.AlignCenter, editable=True)
            self._set_aligned_text(row, self.COL_NET, self._format_weight(net), Qt.AlignRight | Qt.AlignVCenter, editable=False)

        for pallet, rows in grouped_rows.items():
            pallet_weight = float(self._pallet_weights.get(pallet, 0.0))
            for index, row in enumerate(rows):
                net = self._cell_float(row, self.COL_NET)
                gross = net + (pallet_weight if index == 0 else 0.0)
                self._set_aligned_text(row, self.COL_GROSS, self._format_weight(gross), Qt.AlignRight | Qt.AlignVCenter, editable=False)
        self.table.blockSignals(False)
        self._refresh_summary()

    def _refresh_summary(self):
        visible_rows = self._visible_rows()
        selected_view = self._current_view_pallet()

        total_qty = sum(self._cell_float(row, self.COL_QTY) for row in visible_rows)
        total_net = sum(self._cell_float(row, self.COL_NET) for row in visible_rows)
        total_gross = sum(self._cell_float(row, self.COL_GROSS) for row in visible_rows)
        pallet_count = len(self._pallet_order) if selected_view == self.VIEW_ALL else (1 if selected_view in self._pallet_order else 0)

        self.sum_pallets.setText(str(pallet_count))
        self.sum_pieces.setText(f"{total_qty:.0f} PCS" if total_qty.is_integer() else f"{total_qty:.3f} PCS")
        self.sum_net.setText(self._format_weight(total_net))
        self.sum_gross.setText(self._format_weight(total_gross))

    def _build_header_payload(self) -> Dict[str, Any]:
        return {
            "packing_list_number": self.packing_list_number_input.text().strip(),
            "packing_date": self.packing_date_input.date().toString("yyyy-MM-dd"),
            "customer_id": int(self.customer_input.property("customer_id") or 0),
            "consignee": self.consignee_input.text().strip(),
            "notify_party": self.notify_party_input.text().strip(),
            "invoice_number": self.invoice_number_input.text().strip(),
            "proforma_number": self.proforma_number_input.text().strip(),
            "container_no": self.container_no_input.text().strip(),
            "seal_no": self.seal_no_input.text().strip(),
            "country": self.country_input.text().strip(),
            "port_of_loading": self.port_loading_input.text().strip(),
            "port_of_discharge": self.port_discharge_input.text().strip(),
            "delivery_terms": self.delivery_terms_input.text().strip(),
            "payment_terms": self.payment_terms_input.text().strip(),
            "estimated_delivery": self.estimated_delivery_input.text().strip(),
            "currency": self.currency_combo.currentText().strip() or "USD",
            "notes": self.notes_input.toPlainText().strip(),
            "source_type": self.source_type,
            "source_number": self.source_number,
            "total_volume": 0,
        }

    def _build_pallet_payload(self) -> List[Dict[str, Any]]:
        return [
            {"pallet_no": pallet, "pallet_weight": float(self._pallet_weights.get(pallet, 0.0)), "notes": ""}
            for pallet in self._pallet_order
        ]

    def _build_items_payload(self) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        for row in range(self.table.rowCount()):
            stock_item = self.table.item(row, self.COL_STOCK_CODE)
            if stock_item is None:
                continue
            stock_id = int(stock_item.data(Qt.UserRole + 1) or 0)
            if stock_id <= 0:
                continue
            items.append(
                {
                    "pallet_no": self._cell_text(row, self.COL_PALLET),
                    "stock_id": stock_id,
                    "stock_code": self._cell_text(row, self.COL_STOCK_CODE),
                    "description": self._cell_text(row, self.COL_DESCRIPTION),
                    "hs_code": self._cell_text(row, self.COL_HS),
                    "quantity": self._cell_float(row, self.COL_QTY),
                    "unit": self._cell_text(row, self.COL_UNIT),
                    "product_weight": float(stock_item.data(Qt.UserRole + 2) or 0),
                    "net_weight": self._cell_float(row, self.COL_NET),
                    "gross_weight": self._cell_float(row, self.COL_GROSS),
                    "remarks": self._cell_text(row, self.COL_REMARKS),
                }
            )
        return items

    def _validate(self) -> Optional[str]:
        if not self.packing_list_number_input.text().strip():
            return "Packing List numarası zorunludur."
        if int(self.customer_input.property("customer_id") or 0) <= 0:
            return "Müşteri zorunludur ve kaynak belgeden gelmelidir."
        if not self._build_items_payload():
            return "En az bir ürün satırı olmalıdır."
        if not self._pallet_order:
            return "En az bir palet olmalıdır."
        for row in range(self.table.rowCount()):
            if self._cell_text(row, self.COL_STOCK_CODE) and self._cell_float(row, self.COL_QTY) <= 0:
                return f"{row + 1}. satırın miktarı 0'dan büyük olmalıdır."
        return None

    def _save(self) -> bool:
        error = self._validate()
        if error:
            QMessageBox.warning(self, "Uyarı", error)
            return False

        header = self._build_header_payload()
        customer_id = PackingListModel.resolve_or_create_customer_id(
            customer_id=int(header.get("customer_id") or 0),
            cari_kodu=self.customer_code_input.text().strip(),
            firma_unvani=self.customer_input.text().strip(),
            default_currency=self.currency_combo.currentText().strip() or "USD",
        )
        if customer_id <= 0:
            QMessageBox.warning(self, "Uyarı", "Müşteri çözümlenemedi.")
            return False
        header["customer_id"] = customer_id

        created_by = os.getenv("USERNAME") or os.getenv("USER") or "SYSTEM"
        try:
            PackingListModel.save_packing_list(
                header=header,
                pallets=self._build_pallet_payload(),
                items=self._build_items_payload(),
                created_by=created_by,
                existing_packing_list_number=self.existing_packing_list_number if self.is_edit_mode else None,
            )
            self.existing_packing_list_number = header["packing_list_number"]
            self.is_edit_mode = True
            return True
        except Exception as exc:
            QMessageBox.critical(self, "Hata", f"Packing List kaydedilemedi:\n{exc}")
            return False

    def _build_preview_template(self) -> DocumentTemplate:
        lines: List[DocumentLineItem] = []
        for row in range(self.table.rowCount()):
            stock_code = self._cell_text(row, self.COL_STOCK_CODE)
            if not stock_code:
                continue
            desc = self._cell_text(row, self.COL_DESCRIPTION)
            hs = self._cell_text(row, self.COL_HS)
            pallet = self._cell_text(row, self.COL_PALLET)
            remarks = self._cell_text(row, self.COL_REMARKS)
            composed = f"{desc} | Palet: {pallet} | HS: {hs} | {remarks}".strip(" |")
            lines.append(
                DocumentLineItem(
                    line_no=len(lines) + 1,
                    product_code=pallet,
                    description=desc if not remarks else f"{desc}\n{remarks}",
                    quantity=f"{self._cell_float(row, self.COL_QTY):.3f}".rstrip("0").rstrip("."),
                    unit=self._cell_text(row, self.COL_UNIT),
                    unit_price=self._cell_text(row, self.COL_UNIT_WEIGHT),
                    discount="",
                    vat="",
                    total=self._cell_text(row, self.COL_GROSS),
                    amount=self._cell_text(row, self.COL_NET),
                )
            )

        return DocumentTemplate(
            document_title="PACKING LIST",
            filename_base=(self.packing_list_number_input.text().strip() or "packing_list").replace("/", "-"),
            document_kind="PACKING_LIST",
            invoice_number=self.packing_list_number_input.text().strip(),
            invoice_date=self.packing_date_input.date().toString("yyyy-MM-dd"),
            currency=self.currency_combo.currentText().strip() or "USD",
            customer_name=self.customer_input.text().strip(),
            customer_company_name=self.customer_input.text().strip(),
            customer_country=self.country_input.text().strip(),
            customer_code=self.customer_code_input.text().strip(),
            bill_to_company=self.consignee_input.text().strip(),
            ship_to_company=self.notify_party_input.text().strip(),
            payment_terms=self.payment_terms_input.text().strip(),
            delivery_terms=self.delivery_terms_input.text().strip(),
            estimated_delivery=self.estimated_delivery_input.text().strip(),
            packing_type=self.container_no_input.text().strip(),
            subtotal=self.sum_net.text().strip(),
            net_total=self.sum_net.text().strip(),
            grand_total=self.sum_gross.text().strip(),
            notes=self.notes_input.toPlainText().strip(),
            terms_conditions=(
                f"Invoice No: {self.invoice_number_input.text().strip()}\n"
                f"Proforma No: {self.proforma_number_input.text().strip()}\n"
                f"Container No: {self.container_no_input.text().strip()}\n"
                f"Seal No: {self.seal_no_input.text().strip()}\n"
                f"Port of Loading: {self.port_loading_input.text().strip()}\n"
                f"Port of Discharge: {self.port_discharge_input.text().strip()}"
            ),
            items=lines,
        )

    def _on_preview(self):
        window = DocumentPreviewWindow(self._build_preview_template(), parent=self)
        window.show()
        window.raise_()
        window.activateWindow()

    def _on_save(self):
        if self._save():
            QMessageBox.information(self, "Başarılı", "Packing List başarıyla kaydedildi.")

    def _on_save_close(self):
        if self._save():
            self.accept()