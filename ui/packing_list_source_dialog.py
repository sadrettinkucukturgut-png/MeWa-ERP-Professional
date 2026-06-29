from typing import Any, Dict, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from models.packing_list_model import PackingListModel


class PackingListSourceDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Source Document")
        self.resize(860, 520)
        self.selected: Optional[Dict[str, Any]] = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        header = QLabel("Packing List must be generated from Proforma or Export Sales Invoice")
        header.setStyleSheet("font-weight:700; color:#e2e8f0;")
        layout.addWidget(header)

        search_row = QHBoxLayout()
        search_row.addWidget(QLabel("Search"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Source No, Customer, Customer Code")
        self.search_input.textChanged.connect(self._load)
        search_row.addWidget(self.search_input, 1)
        layout.addLayout(search_row)

        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "Source Type",
            "Source Number",
            "Date",
            "Customer",
            "Customer Code",
            "Currency",
            "Total",
            "Status",
        ])
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.doubleClicked.connect(self._accept_selected)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.btn_select = QPushButton("Select")
        self.btn_cancel = QPushButton("Cancel")
        self.btn_select.clicked.connect(self._accept_selected)
        self.btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(self.btn_select)
        btn_row.addWidget(self.btn_cancel)
        layout.addLayout(btn_row)

        self.setStyleSheet(
            "QDialog{background:#0b1220;} QLabel{color:#e2e8f0;}"
            "QLineEdit{background:#0f172a; color:#e2e8f0; border:1px solid #334155; border-radius:8px; padding:6px;}"
            "QPushButton{background:#1e293b; color:#f8fafc; border:1px solid #334155; border-radius:8px; padding:7px 12px;}"
            "QPushButton:hover{background:#334155;}"
            "QTableWidget{background:#111827; alternate-background-color:#0f172a; color:#e5e7eb; border:1px solid #334155;}"
            "QHeaderView::section{background:#1f2937; color:#e5e7eb; padding:8px 6px;}"
        )

        self._rows: list[Dict[str, Any]] = []
        self._load("")

    def _load(self, keyword: str):
        self._rows = PackingListModel.source_documents(keyword)
        self.table.setRowCount(len(self._rows))
        for r, row in enumerate(self._rows):
            values = [
                str(row.get("source_type") or ""),
                str(row.get("source_number") or ""),
                str(row.get("source_date") or ""),
                str(row.get("customer_name") or ""),
                str(row.get("customer_code") or ""),
                str(row.get("currency") or "USD"),
                f"{float(row.get('grand_total') or 0):,.2f}",
                str(row.get("status") or ""),
            ]
            for c, value in enumerate(values):
                self.table.setItem(r, c, QTableWidgetItem(value))

        if self._rows:
            self.table.selectRow(0)
            self.table.setCurrentCell(0, 0)

    def _accept_selected(self):
        row = self.table.currentRow()
        if row < 0 or row >= len(self._rows):
            return
        self.selected = dict(self._rows[row])
        self.accept()

    @classmethod
    def select_source(cls, parent=None) -> Optional[Dict[str, Any]]:
        dialog = cls(parent)
        if dialog.exec():
            return dialog.selected
        return None
