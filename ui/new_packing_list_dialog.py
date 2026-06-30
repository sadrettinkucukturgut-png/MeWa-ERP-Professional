import os
from typing import Any, Dict, List, Optional

from PySide6.QtCore import QDate, QSettings, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from models.packing_list_model import PackingListModel
from models.packing_model import PackingItem
from services.document_preview_engine import DocumentPreviewWindow
from services.packing_renderer_service import PackingRendererService
from services.pallet_assignment_service import PalletAssignmentService
from services.pallet_manager_service import PalletManagerService
from services.weight_calculator_service import WeightCalculatorService


class MoveToPalletDialog(QDialog):
    CREATE_NEW_OPTION = "Create New Pallet"

    def __init__(self, product_count: int, pallets: List[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Move To Pallet")
        self.selected_destination = ""

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"Selected products: {int(product_count)}"))
        layout.addWidget(QLabel("Destination"))

        self.destination_combo = QComboBox()
        self.destination_combo.addItems(pallets)
        self.destination_combo.addItem(self.CREATE_NEW_OPTION)
        layout.addWidget(self.destination_combo)

        buttons = QHBoxLayout()
        buttons.addStretch()

        move_btn = QPushButton("Move")
        cancel_btn = QPushButton("Cancel")
        move_btn.clicked.connect(self._accept)
        cancel_btn.clicked.connect(self.reject)
        buttons.addWidget(move_btn)
        buttons.addWidget(cancel_btn)
        layout.addLayout(buttons)

        self.setStyleSheet(
            "QDialog{background:#0b1220;} QLabel{color:#e2e8f0;}"
            "QComboBox{background:#0f172a; color:#e2e8f0; border:1px solid #334155; border-radius:8px; padding:6px;}"
            "QPushButton{background:#1e293b; color:#f8fafc; border:1px solid #334155; border-radius:8px; padding:8px 12px;}"
            "QPushButton:hover{background:#334155;}"
        )

    def _accept(self):
        self.selected_destination = self.destination_combo.currentText().strip()
        self.accept()


class SplitToPalletDialog(QDialog):
    CREATE_NEW_OPTION = "Create New Pallet"

    def __init__(self, item: PackingItem, pallets: List[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Split To Pallet")
        self.selected_destination = ""
        self.move_quantity = 0.0

        quantity_text = f"{float(item.quantity):.3f}".rstrip("0").rstrip(".")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Product"))
        layout.addWidget(QLabel(item.description or item.stock_code))
        layout.addWidget(QLabel("Original Quantity"))
        layout.addWidget(QLabel(f"{quantity_text} {item.unit}".strip()))
        layout.addWidget(QLabel("Move Quantity"))

        self.move_qty_input = QDoubleSpinBox()
        self.move_qty_input.setDecimals(3)
        self.move_qty_input.setMinimum(0.001)
        self.move_qty_input.setMaximum(max(0.001, float(item.quantity) - 0.001))
        self.move_qty_input.setValue(min(1.0, self.move_qty_input.maximum()))
        layout.addWidget(self.move_qty_input)

        layout.addWidget(QLabel("Target Pallet"))
        self.destination_combo = QComboBox()
        self.destination_combo.addItems(pallets)
        self.destination_combo.addItem(self.CREATE_NEW_OPTION)
        layout.addWidget(self.destination_combo)

        buttons = QHBoxLayout()
        buttons.addStretch()
        split_btn = QPushButton("Split")
        cancel_btn = QPushButton("Cancel")
        split_btn.clicked.connect(self._accept)
        cancel_btn.clicked.connect(self.reject)
        buttons.addWidget(split_btn)
        buttons.addWidget(cancel_btn)
        layout.addLayout(buttons)

        self.setStyleSheet(
            "QDialog{background:#0b1220;} QLabel{color:#e2e8f0;}"
            "QComboBox,QDoubleSpinBox{background:#0f172a; color:#e2e8f0; border:1px solid #334155; border-radius:8px; padding:6px;}"
            "QPushButton{background:#1e293b; color:#f8fafc; border:1px solid #334155; border-radius:8px; padding:8px 12px;}"
            "QPushButton:hover{background:#334155;}"
        )

    def _accept(self):
        self.selected_destination = self.destination_combo.currentText().strip()
        self.move_quantity = float(self.move_qty_input.value())
        self.accept()


class NewPackingListDialog(QDialog):
    COL_ROW = 0
    COL_PALLET = 1
    COL_STOCK_CODE = 2
    COL_DESCRIPTION = 3
    COL_HS = 4
    COL_QTY = 5
    COL_UNIT = 6
    COL_QTY_WEIGHT = 7
    COL_NET = 8
    COL_GROSS = 9
    COL_REMARKS = 10

    DEFAULT_PALLET = "Pallet 1"

    def __init__(
        self,
        source_type: Optional[str] = None,
        source_number: Optional[str] = None,
        packing_list_number: Optional[str] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Packing List")
        self.resize(1480, 860)
        self.setMinimumSize(1240, 740)

        self.settings = QSettings("MeWa", "ERP")

        self.source_type = str(source_type or "").strip()
        self.source_number = str(source_number or "").strip()
        self.existing_packing_list_number = str(packing_list_number or "").strip()
        self.is_edit_mode = bool(self.existing_packing_list_number)

        self._items: List[PackingItem] = []
        self._pallet_order: List[str] = []
        self._pallet_weights: Dict[str, float] = {}
        self._selected_pallet_filter = ""

        self._build_ui()

        if self.is_edit_mode:
            self._load_existing(self.existing_packing_list_number)
        else:
            self.packing_list_number_input.setText(PackingListModel.packing_list_number_generate())
            self.packing_date_input.setDate(QDate.currentDate())
            self._ensure_pallet(self.DEFAULT_PALLET)
            if self.source_type and self.source_number:
                self._import_from_source(self.source_type, self.source_number)

        self._refresh_all_views(select_pallet=self._selected_pallet_filter or self.DEFAULT_PALLET)

    def closeEvent(self, event):
        self._save_splitter_state()
        super().closeEvent(event)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        title = QLabel("Packing List")
        title.setStyleSheet("font-size:16px; font-weight:700; color:#f8fafc;")
        root.addWidget(title)

        root.addWidget(self._build_header_form())

        self.main_splitter = QSplitter(Qt.Horizontal)
        self.main_splitter.setChildrenCollapsible(False)
        self.main_splitter.addWidget(self._build_pallet_navigator_panel())
        self.main_splitter.addWidget(self._build_products_panel())
        root.addWidget(self.main_splitter, 1)
        self._load_splitter_state()

        self.setStyleSheet(
            "QDialog{background:#0b1220;} QLabel{color:#e2e8f0;}"
            "QLineEdit,QComboBox,QDateEdit,QTextEdit{background:#0f172a; color:#e2e8f0; border:1px solid #334155; border-radius:8px; padding:6px;}"
            "QPushButton{background:#1e293b; color:#f8fafc; border:1px solid #334155; border-radius:8px; padding:8px 12px;}"
            "QPushButton:hover{background:#334155;}"
            "QTableWidget{background:#111827; alternate-background-color:#0f172a; color:#e5e7eb; border:1px solid #334155;}"
            "QHeaderView::section{background:#1f2937; color:#e5e7eb; padding:8px 6px;}"
            "QToolBar{background:#0f172a; border:1px solid #334155; border-radius:8px; spacing:6px; padding:4px;}"
        )

    def _build_header_form(self) -> QWidget:
        frame = QFrame()
        frame.setStyleSheet("QFrame{background:#0f172a; border:1px solid #334155; border-radius:10px;}")
        form_layout = QGridLayout(frame)
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
        self.notes_input.setFixedHeight(40)

        compact_fields = [
            ("Packing List No", self.packing_list_number_input),
            ("Date", self.packing_date_input),
            ("Customer", self.customer_input),
            ("Customer Code", self.customer_code_input),
            ("Invoice No", self.invoice_number_input),
            ("Proforma No", self.proforma_number_input),
            ("Consignee", self.consignee_input),
            ("Notify Party", self.notify_party_input),
            ("Container No", self.container_no_input),
            ("Seal No", self.seal_no_input),
            ("Port of Loading", self.port_loading_input),
            ("Port of Discharge", self.port_discharge_input),
            ("Country", self.country_input),
            ("Delivery Terms", self.delivery_terms_input),
            ("Payment Terms", self.payment_terms_input),
            ("Estimated Delivery", self.estimated_delivery_input),
            ("Currency", self.currency_combo),
            ("Notes", self.notes_input),
        ]

        for index, (label_text, widget) in enumerate(compact_fields):
            row = index // 4
            col = (index % 4) * 2
            form_layout.addWidget(QLabel(label_text), row, col)
            form_layout.addWidget(widget, row, col + 1)

        return frame

    def _build_pallet_navigator_panel(self) -> QWidget:
        panel = QFrame()
        panel.setStyleSheet("QFrame{background:#0f172a; border:1px solid #334155; border-radius:10px;}")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        layout.addWidget(QLabel("Pallet Navigator"))

        toolbar_row = QHBoxLayout()
        self.btn_new_pallet = QPushButton("+ Yeni Palet")
        self.btn_rename_pallet = QPushButton("Rename")
        self.btn_delete_pallet = QPushButton("Delete Empty")
        self.btn_new_pallet.clicked.connect(self._create_new_pallet)
        self.btn_rename_pallet.clicked.connect(self._rename_selected_pallet)
        self.btn_delete_pallet.clicked.connect(self._delete_selected_pallet)
        toolbar_row.addWidget(self.btn_new_pallet)
        toolbar_row.addWidget(self.btn_rename_pallet)
        toolbar_row.addWidget(self.btn_delete_pallet)
        layout.addLayout(toolbar_row)

        self.pallet_table = QTableWidget()
        self.pallet_table.setColumnCount(5)
        self.pallet_table.setHorizontalHeaderLabels(["Pallet", "Products", "Qty", "Net", "Gross"])
        self.pallet_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.pallet_table.setSelectionMode(QTableWidget.SingleSelection)
        self.pallet_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.pallet_table.verticalHeader().setVisible(False)
        self.pallet_table.setAlternatingRowColors(True)
        self.pallet_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.pallet_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.pallet_table.customContextMenuRequested.connect(self._show_pallet_context_menu)
        self.pallet_table.itemSelectionChanged.connect(self._on_pallet_selection_changed)
        layout.addWidget(self.pallet_table, 1)

        return panel

    def _build_products_panel(self) -> QWidget:
        panel = QFrame()
        panel.setStyleSheet("QFrame{background:#0f172a; border:1px solid #334155; border-radius:10px;}")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        self.products_toolbar = QToolBar()
        self.products_toolbar.setMovable(False)
        self.btn_move_to_pallet = QPushButton("Split To Pallet")
        self.btn_duplicate = QPushButton("Duplicate")
        self.btn_delete_rows = QPushButton("Delete")
        self.btn_edit_remarks = QPushButton("Edit Remarks")
        self.btn_move_to_pallet.clicked.connect(self._split_selected_product)
        self.btn_duplicate.clicked.connect(self._duplicate_selected_products)
        self.btn_delete_rows.clicked.connect(self._delete_selected_products)
        self.btn_edit_remarks.clicked.connect(self._edit_selected_remarks)
        self.products_toolbar.addWidget(self.btn_move_to_pallet)
        self.products_toolbar.addWidget(self.btn_duplicate)
        self.products_toolbar.addWidget(self.btn_delete_rows)
        self.products_toolbar.addWidget(self.btn_edit_remarks)
        layout.addWidget(self.products_toolbar)

        self.table = QTableWidget()
        self.table.setColumnCount(11)
        self.table.setHorizontalHeaderLabels(
            [
                "#",
                "Pallet",
                "Stock Code",
                "Description",
                "HS Code",
                "Quantity",
                "Unit",
                "Quantity Weight",
                "Net Weight",
                "Gross Weight",
                "Remarks",
            ]
        )
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.ExtendedSelection)
        self.table.setWordWrap(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.itemChanged.connect(self._on_table_item_changed)
        self.table.itemSelectionChanged.connect(self._update_action_states)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_product_context_menu)
        self.table.verticalHeader().setDefaultSectionSize(38)
        self.table.setColumnWidth(self.COL_ROW, 44)
        self.table.setColumnWidth(self.COL_PALLET, 110)
        self.table.setColumnWidth(self.COL_STOCK_CODE, 120)
        self.table.setColumnWidth(self.COL_DESCRIPTION, 310)
        self.table.setColumnWidth(self.COL_HS, 100)
        self.table.setColumnWidth(self.COL_QTY, 90)
        self.table.setColumnWidth(self.COL_UNIT, 80)
        self.table.setColumnWidth(self.COL_QTY_WEIGHT, 120)
        self.table.setColumnWidth(self.COL_NET, 120)
        self.table.setColumnWidth(self.COL_GROSS, 120)
        self.table.setColumnWidth(self.COL_REMARKS, 220)
        layout.addWidget(self.table, 1)

        bottom_row = QHBoxLayout()
        self.summary_frame = QFrame()
        self.summary_frame.setStyleSheet("QFrame{background:#111827; border:1px solid #334155; border-radius:10px;}")
        summary_layout = QGridLayout(self.summary_frame)
        summary_layout.setContentsMargins(10, 8, 10, 8)
        summary_layout.setHorizontalSpacing(14)
        summary_layout.setVerticalSpacing(6)

        self.sum_pallets = QLabel("0")
        self.sum_pieces = QLabel("0")
        self.sum_net = QLabel("0.00 KG")
        self.sum_gross = QLabel("0.00 KG")

        summary_fields = [
            ("TOTAL PALLETS", self.sum_pallets),
            ("TOTAL PIECES", self.sum_pieces),
            ("TOTAL NET WEIGHT", self.sum_net),
            ("TOTAL GROSS WEIGHT", self.sum_gross),
        ]
        for i, (label_text, value_label) in enumerate(summary_fields):
            summary_layout.addWidget(QLabel(label_text), i, 0)
            summary_layout.addWidget(value_label, i, 1)
            value_label.setStyleSheet("font-size:14px; font-weight:700; color:#f8fafc;")
        bottom_row.addWidget(self.summary_frame, 0)

        action_row = QHBoxLayout()
        action_row.addStretch()
        self.btn_preview = QPushButton("Preview")
        self.btn_save = QPushButton("Save")
        self.btn_save_close = QPushButton("Save & Close")
        self.btn_cancel = QPushButton("Cancel")
        self.btn_preview.clicked.connect(self._on_preview)
        self.btn_save.clicked.connect(self._on_save)
        self.btn_save_close.clicked.connect(self._on_save_close)
        self.btn_cancel.clicked.connect(self.reject)
        action_row.addWidget(self.btn_preview)
        action_row.addWidget(self.btn_save)
        action_row.addWidget(self.btn_save_close)
        action_row.addWidget(self.btn_cancel)

        action_frame = QFrame()
        action_frame.setStyleSheet("QFrame{background:#111827; border:1px solid #334155; border-radius:10px;}")
        action_frame.setLayout(action_row)
        bottom_row.addWidget(action_frame, 1)

        layout.addLayout(bottom_row)

        return panel

    def _load_splitter_state(self):
        raw = self.settings.value("packing_list_dialog/main_splitter_sizes", [320, 1020])
        try:
            sizes = [int(value) for value in raw]
        except Exception:
            sizes = [320, 1020]
        if len(sizes) >= 2:
            self.main_splitter.setSizes(sizes[:2])

    def _save_splitter_state(self):
        self.settings.setValue("packing_list_dialog/main_splitter_sizes", self.main_splitter.sizes())

    def _ensure_pallet(self, pallet_no: str, weight: float = 25.0):
        PalletManagerService.ensure_pallet(self._pallet_order, self._pallet_weights, pallet_no, default_weight=weight)

    def _create_new_pallet(self) -> str:
        new_pallet = PalletManagerService.next_auto_name(self._pallet_order, prefix="Pallet")
        self._ensure_pallet(new_pallet, 25.0)
        self._refresh_all_views(select_pallet=new_pallet)
        return new_pallet

    def _selected_pallet(self) -> str:
        row = self.pallet_table.currentRow()
        if row < 0:
            return ""
        item = self.pallet_table.item(row, 0)
        return "" if item is None else item.text().strip()

    def _selected_item_indexes(self) -> List[int]:
        indexes: List[int] = []
        for selected_range in self.table.selectedRanges():
            for row in range(selected_range.topRow(), selected_range.bottomRow() + 1):
                marker = self.table.item(row, self.COL_ROW)
                if marker is None:
                    continue
                model_index = marker.data(Qt.UserRole)
                if isinstance(model_index, int):
                    indexes.append(model_index)
        return sorted(set(indexes))

    def _format_qty(self, value: float) -> str:
        text = f"{float(value):.3f}"
        return text.rstrip("0").rstrip(".") if "." in text else text

    def _format_weight(self, value: float) -> str:
        return f"{float(value):.3f} KG"

    def _to_float(self, text: str) -> float:
        cleaned = str(text or "").replace("KG", "").replace("PCS", "").strip()
        try:
            return float(cleaned or 0)
        except ValueError:
            return 0.0

    def _refresh_all_views(self, select_pallet: str = ""):
        self._refresh_pallet_navigator(select_pallet=select_pallet)
        self._refresh_product_table()
        self._refresh_summary()
        self._update_action_states()

    def _refresh_pallet_navigator(self, select_pallet: str = ""):
        stats = WeightCalculatorService.all_pallet_stats(self._pallet_order, self._pallet_weights, self._items)

        self.pallet_table.blockSignals(True)
        self.pallet_table.setRowCount(len(self._pallet_order))
        for row, pallet_name in enumerate(self._pallet_order):
            pallet_stat = stats.get(pallet_name)
            values = [
                pallet_name,
                str(int(pallet_stat.product_count if pallet_stat else 0)),
                self._format_qty(pallet_stat.total_quantity if pallet_stat else 0),
                self._format_weight(pallet_stat.total_net_weight if pallet_stat else 0),
                self._format_weight(pallet_stat.total_gross_weight if pallet_stat else 0),
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                if col > 0:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.pallet_table.setItem(row, col, item)
        self.pallet_table.blockSignals(False)

        target = select_pallet or self._selected_pallet_filter
        if not target and self._pallet_order:
            target = self._pallet_order[0]

        selected_row = -1
        for row in range(self.pallet_table.rowCount()):
            item = self.pallet_table.item(row, 0)
            if item is not None and item.text().strip() == target:
                selected_row = row
                break

        if selected_row >= 0:
            self.pallet_table.selectRow(selected_row)
            self._selected_pallet_filter = target
        else:
            self._selected_pallet_filter = ""

    def _refresh_product_table(self):
        gross_by_index = WeightCalculatorService.item_gross_weights(self._pallet_order, self._pallet_weights, self._items)

        visible_indexes: List[int] = []
        for index, item in enumerate(self._items):
            if self._selected_pallet_filter and item.pallet_no != self._selected_pallet_filter:
                continue
            visible_indexes.append(index)

        self.table.blockSignals(True)
        self.table.setRowCount(len(visible_indexes))

        for row, item_index in enumerate(visible_indexes):
            item = self._items[item_index]
            net = WeightCalculatorService.item_net_weight(item)
            gross = gross_by_index.get(item_index, net)

            values = [
                str(row + 1),
                item.pallet_no,
                item.stock_code,
                item.description,
                item.hs_code,
                self._format_qty(item.quantity),
                item.unit,
                self._format_weight(item.quantity_weight),
                self._format_weight(net),
                self._format_weight(gross),
                item.remarks,
            ]

            for col, value in enumerate(values):
                cell = QTableWidgetItem(value)
                editable = col in (self.COL_QTY, self.COL_REMARKS)
                if not editable:
                    cell.setFlags(cell.flags() & ~Qt.ItemIsEditable)
                if col in (self.COL_ROW, self.COL_QTY, self.COL_QTY_WEIGHT, self.COL_NET, self.COL_GROSS):
                    cell.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                cell.setData(Qt.UserRole, item_index)
                self.table.setItem(row, col, cell)

        self.table.blockSignals(False)

    def _refresh_summary(self):
        totals = WeightCalculatorService.totals(self._pallet_order, self._pallet_weights, self._items)
        self.sum_pallets.setText(str(int(totals.total_pallets)))
        self.sum_pieces.setText(self._format_qty(totals.total_pieces))
        self.sum_net.setText(self._format_weight(totals.total_net_weight))
        self.sum_gross.setText(self._format_weight(totals.total_gross_weight))

    def _on_pallet_selection_changed(self):
        selected = self._selected_pallet()
        if not selected:
            return
        self._selected_pallet_filter = selected
        self._refresh_product_table()
        self._update_action_states()

    def _on_table_item_changed(self, item: QTableWidgetItem):
        if item is None:
            return
        model_index = item.data(Qt.UserRole)
        if not isinstance(model_index, int) or model_index < 0 or model_index >= len(self._items):
            return

        row_item = self._items[model_index]
        if item.column() == self.COL_QTY:
            quantity = max(0.0, self._to_float(item.text()))
            row_item.quantity = quantity
        elif item.column() == self.COL_REMARKS:
            row_item.remarks = item.text().strip()

        self._refresh_all_views(select_pallet=self._selected_pallet_filter)

    def _update_action_states(self):
        has_selected_rows = bool(self._selected_item_indexes())
        has_selected_pallet = bool(self._selected_pallet())
        self.btn_move_to_pallet.setEnabled(has_selected_rows)
        self.btn_duplicate.setEnabled(has_selected_rows)
        self.btn_delete_rows.setEnabled(has_selected_rows)
        self.btn_edit_remarks.setEnabled(has_selected_rows)
        self.btn_rename_pallet.setEnabled(has_selected_pallet)
        self.btn_delete_pallet.setEnabled(has_selected_pallet)

    def _move_selected_products(self):
        indexes = self._selected_item_indexes()
        if not indexes:
            return

        dialog = MoveToPalletDialog(product_count=len(indexes), pallets=self._pallet_order, parent=self)
        if not dialog.exec() or not dialog.selected_destination:
            return

        destination = dialog.selected_destination
        if destination == MoveToPalletDialog.CREATE_NEW_OPTION:
            destination = self._create_new_pallet()

        PalletAssignmentService.move_items_to_pallet(self._items, indexes, destination)
        self._refresh_all_views(select_pallet=destination)

    def _split_selected_product(self):
        indexes = self._selected_item_indexes()
        if not indexes:
            return
        if len(indexes) > 1:
            QMessageBox.warning(self, "Warning", "Split works with one product row at a time.")
            return

        source_index = indexes[0]
        source_item = self._items[source_index]

        dialog = SplitToPalletDialog(source_item, self._pallet_order, parent=self)
        if not dialog.exec() or not dialog.selected_destination:
            return

        destination = dialog.selected_destination
        if destination == SplitToPalletDialog.CREATE_NEW_OPTION:
            destination = self._create_new_pallet()

        success, message = PalletAssignmentService.split_item_to_pallet(
            self._items,
            source_index,
            float(dialog.move_quantity),
            destination,
        )
        if not success:
            QMessageBox.warning(self, "Warning", message)
            return
        self._refresh_all_views(select_pallet=destination)

    def _duplicate_selected_products(self):
        indexes = self._selected_item_indexes()
        if not indexes:
            return
        duplicated = PalletAssignmentService.duplicate_items(self._items, indexes)
        self._items.extend(duplicated)
        self._refresh_all_views(select_pallet=self._selected_pallet_filter)

    def _delete_selected_products(self):
        indexes = self._selected_item_indexes()
        if not indexes:
            return
        PalletAssignmentService.delete_items(self._items, indexes)
        self._refresh_all_views(select_pallet=self._selected_pallet_filter)

    def _edit_selected_remarks(self):
        indexes = self._selected_item_indexes()
        if not indexes:
            return
        if len(indexes) > 1:
            remark, ok = QInputDialog.getText(self, "Edit Remarks", "Remarks for selected products:")
            if not ok:
                return
            for index in indexes:
                self._items[index].remarks = str(remark or "").strip()
        else:
            index = indexes[0]
            remark, ok = QInputDialog.getText(
                self,
                "Edit Remarks",
                "Remarks:",
                text=self._items[index].remarks,
            )
            if not ok:
                return
            self._items[index].remarks = str(remark or "").strip()
        self._refresh_all_views(select_pallet=self._selected_pallet_filter)

    def _rename_selected_pallet(self):
        current = self._selected_pallet()
        if not current:
            return
        new_name, ok = QInputDialog.getText(self, "Rename Pallet", "New pallet name:", text=current)
        if not ok:
            return

        success, message = PalletManagerService.rename_pallet(
            self._pallet_order,
            self._pallet_weights,
            self._items,
            current,
            str(new_name or ""),
        )
        if not success:
            QMessageBox.warning(self, "Warning", message)
            return
        self._refresh_all_views(select_pallet=str(new_name or "").strip())

    def _delete_selected_pallet(self):
        pallet = self._selected_pallet()
        if not pallet:
            return

        success, message = PalletManagerService.delete_empty_pallet(
            self._pallet_order,
            self._pallet_weights,
            self._items,
            pallet,
        )
        if not success:
            QMessageBox.warning(self, "Warning", message)
            return

        if not self._pallet_order:
            self._ensure_pallet(self.DEFAULT_PALLET)
        select_pallet = self._pallet_order[0] if self._pallet_order else ""
        self._refresh_all_views(select_pallet=select_pallet)

    def _show_product_context_menu(self, pos):
        menu = QMenu(self)
        action_move = menu.addAction("Split To Pallet")
        action_duplicate = menu.addAction("Duplicate")
        action_delete = menu.addAction("Delete")
        action_edit_remarks = menu.addAction("Edit Remarks")

        action = menu.exec(self.table.viewport().mapToGlobal(pos))
        if action == action_move:
            self._split_selected_product()
        elif action == action_duplicate:
            self._duplicate_selected_products()
        elif action == action_delete:
            self._delete_selected_products()
        elif action == action_edit_remarks:
            self._edit_selected_remarks()

    def _show_pallet_context_menu(self, pos):
        menu = QMenu(self)
        action_rename = menu.addAction("Rename")
        action_delete = menu.addAction("Delete Empty")
        action_print = menu.addAction("Print Pallet")

        action = menu.exec(self.pallet_table.viewport().mapToGlobal(pos))
        if action == action_rename:
            self._rename_selected_pallet()
        elif action == action_delete:
            self._delete_selected_pallet()
        elif action == action_print:
            selected = self._selected_pallet()
            if selected:
                self._open_preview(selected_pallet=selected)

    def _import_from_source(self, source_type: str, source_number: str):
        detail = PackingListModel.source_detail(source_type, source_number)
        if detail is None:
            QMessageBox.warning(self, "Warning", "Source document not found.")
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

        self._items = []
        self._pallet_order = []
        self._pallet_weights = {}
        self._ensure_pallet(self.DEFAULT_PALLET)

        for src_item in detail.get("items", []):
            self._items.append(
                PackingItem(
                    stock_id=int(src_item.get("stock_id") or 0),
                    stock_code=str(src_item.get("stock_code") or ""),
                    description=str(src_item.get("description") or src_item.get("product_name") or ""),
                    hs_code=str(src_item.get("hs_code") or ""),
                    quantity=float(src_item.get("quantity") or 0),
                    unit=str(src_item.get("unit") or ""),
                    quantity_weight=float(src_item.get("product_weight") or src_item.get("weight") or 0),
                    pallet_no=self.DEFAULT_PALLET,
                    remarks=str(src_item.get("remarks") or ""),
                )
            )

    def _load_existing(self, packing_list_number: str):
        detail = PackingListModel.packing_list_detail(packing_list_number)
        if detail is None:
            QMessageBox.warning(self, "Warning", "Packing List not found.")
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

        self._items = []
        self._pallet_order = []
        self._pallet_weights = {}
        for pallet in detail.get("pallets", []):
            self._ensure_pallet(str(pallet.get("pallet_no") or ""), float(pallet.get("pallet_weight") or 0))
        if not self._pallet_order:
            self._ensure_pallet(self.DEFAULT_PALLET)

        for item in detail.get("items", []):
            pallet_no = str(item.get("pallet_no") or self.DEFAULT_PALLET)
            self._ensure_pallet(pallet_no, self._pallet_weights.get(pallet_no, 25.0))
            self._items.append(
                PackingItem(
                    stock_id=int(item.get("stock_id") or 0),
                    stock_code=str(item.get("stock_code") or ""),
                    description=str(item.get("description") or ""),
                    hs_code=str(item.get("hs_code") or ""),
                    quantity=float(item.get("quantity") or 0),
                    unit=str(item.get("unit") or ""),
                    quantity_weight=float(item.get("product_weight") or 0),
                    pallet_no=pallet_no,
                    remarks=str(item.get("remarks") or ""),
                )
            )

    def load_duplicate_data(self, packing_list_number: str):
        detail = PackingListModel.packing_list_detail(packing_list_number)
        if detail is None:
            QMessageBox.warning(self, "Warning", "Packing List not found for duplication.")
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
        self._items = []

        for pallet in detail.get("pallets", []):
            self._ensure_pallet(str(pallet.get("pallet_no") or ""), float(pallet.get("pallet_weight") or 0))
        if not self._pallet_order:
            self._ensure_pallet(self.DEFAULT_PALLET)

        for item in detail.get("items", []):
            pallet_no = str(item.get("pallet_no") or self.DEFAULT_PALLET)
            self._items.append(
                PackingItem(
                    stock_id=int(item.get("stock_id") or 0),
                    stock_code=str(item.get("stock_code") or ""),
                    description=str(item.get("description") or ""),
                    hs_code=str(item.get("hs_code") or ""),
                    quantity=float(item.get("quantity") or 0),
                    unit=str(item.get("unit") or ""),
                    quantity_weight=float(item.get("product_weight") or 0),
                    pallet_no=pallet_no,
                    remarks=str(item.get("remarks") or ""),
                )
            )

        self._refresh_all_views(select_pallet=self._pallet_order[0] if self._pallet_order else self.DEFAULT_PALLET)

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
            {
                "pallet_no": pallet,
                "pallet_weight": float(self._pallet_weights.get(pallet, 0.0)),
                "notes": "",
            }
            for pallet in self._pallet_order
        ]

    def _build_items_payload(self) -> List[Dict[str, Any]]:
        gross_by_index = WeightCalculatorService.item_gross_weights(self._pallet_order, self._pallet_weights, self._items)
        items: List[Dict[str, Any]] = []

        for index, item in enumerate(self._items):
            if item.stock_id <= 0 or float(item.quantity) <= 0:
                continue
            items.append(
                {
                    "pallet_no": item.pallet_no,
                    "stock_id": int(item.stock_id),
                    "stock_code": item.stock_code,
                    "description": item.description,
                    "hs_code": item.hs_code,
                    "quantity": float(item.quantity),
                    "unit": item.unit,
                    "product_weight": float(item.quantity_weight),
                    "net_weight": float(WeightCalculatorService.item_net_weight(item)),
                    "gross_weight": float(gross_by_index.get(index, 0.0)),
                    "remarks": item.remarks,
                }
            )
        return items

    def _validate(self) -> Optional[str]:
        if not self.packing_list_number_input.text().strip():
            return "Packing List number is required."
        if int(self.customer_input.property("customer_id") or 0) <= 0:
            return "Customer is required and should be imported from source document."
        if not self._items:
            return "At least one product row is required."
        if not self._pallet_order:
            return "At least one pallet is required."
        for index, item in enumerate(self._items):
            if item.stock_code and float(item.quantity) <= 0:
                return f"Row {index + 1} quantity must be greater than 0."
        return None

    def _save(self) -> bool:
        error = self._validate()
        if error:
            QMessageBox.warning(self, "Warning", error)
            return False

        header = self._build_header_payload()
        customer_id = PackingListModel.resolve_or_create_customer_id(
            customer_id=int(header.get("customer_id") or 0),
            cari_kodu=self.customer_code_input.text().strip(),
            firma_unvani=self.customer_input.text().strip(),
            default_currency=self.currency_combo.currentText().strip() or "USD",
        )
        if customer_id <= 0:
            QMessageBox.warning(self, "Warning", "Customer could not be resolved.")
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
            QMessageBox.critical(self, "Error", f"Packing List could not be saved:\n{exc}")
            return False

    def _build_preview_template(self, selected_pallet: Optional[str] = None):
        gross_by_index = WeightCalculatorService.item_gross_weights(self._pallet_order, self._pallet_weights, self._items)
        return PackingRendererService.build_template(
            packing_list_number=self.packing_list_number_input.text().strip(),
            packing_date=self.packing_date_input.date().toString("yyyy-MM-dd"),
            currency=self.currency_combo.currentText().strip() or "USD",
            customer_name=self.customer_input.text().strip(),
            customer_code=self.customer_code_input.text().strip(),
            country=self.country_input.text().strip(),
            consignee=self.consignee_input.text().strip(),
            notify_party=self.notify_party_input.text().strip(),
            payment_terms=self.payment_terms_input.text().strip(),
            delivery_terms=self.delivery_terms_input.text().strip(),
            estimated_delivery=self.estimated_delivery_input.text().strip(),
            container_no=self.container_no_input.text().strip(),
            invoice_number=self.invoice_number_input.text().strip(),
            proforma_number=self.proforma_number_input.text().strip(),
            seal_no=self.seal_no_input.text().strip(),
            port_loading=self.port_loading_input.text().strip(),
            port_discharge=self.port_discharge_input.text().strip(),
            notes=self.notes_input.toPlainText().strip(),
            items=self._items,
            gross_by_index=gross_by_index,
            selected_pallet=selected_pallet,
        )

    def _open_preview(self, selected_pallet: Optional[str] = None):
        window = DocumentPreviewWindow(self._build_preview_template(selected_pallet=selected_pallet), parent=self)
        window.show()
        window.raise_()
        window.activateWindow()

    def _on_preview(self):
        self._open_preview(selected_pallet=None)

    def _on_save(self):
        if self._save():
            QMessageBox.information(self, "Success", "Packing List saved successfully.")

    def _on_save_close(self):
        if self._save():
            self.accept()
