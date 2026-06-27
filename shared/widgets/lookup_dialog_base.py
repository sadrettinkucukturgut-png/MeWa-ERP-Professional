from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import QAbstractItemView, QDialog, QHBoxLayout, QHeaderView, QLineEdit, QPushButton, QTableWidget, QVBoxLayout


class LookupDialogBase(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.search_input = None
        self.table = None

    def _build_lookup_shell(self, title: str, placeholder: str, headers: list[str], width: int, height: int):
        self.setWindowTitle(title)
        self.resize(width, height)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(placeholder)
        self.search_input.textChanged.connect(self._filter_rows)
        self.search_input.returnPressed.connect(self._accept_first_visible_row)
        layout.addWidget(self.search_input)

        self.table = QTableWidget()
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSortingEnabled(False)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table.setMouseTracking(True)
        self.table.itemActivated.connect(lambda item: self._accept_row(item.row()))
        self.table.itemDoubleClicked.connect(lambda item: self._accept_row(item.row()))
        layout.addWidget(self.table)

        button_row = QHBoxLayout()
        button_row.addStretch()

        self.select_button = QPushButton("Seç")
        self.select_button.clicked.connect(self._accept_current_row)
        self.cancel_button = QPushButton("İptal")
        self.cancel_button.clicked.connect(self.reject)

        button_row.addWidget(self.select_button)
        button_row.addWidget(self.cancel_button)
        layout.addLayout(button_row)

        self.search_input.installEventFilter(self)
        self.table.installEventFilter(self)

        self.setStyleSheet(
            "QDialog{background:#0b1220;} QLabel{color:#e2e8f0;}"
            "QLineEdit{background:#0f172a; color:#e2e8f0; border:1px solid #334155; border-radius:8px; padding:7px;}"
            "QLineEdit:focus{border:1px solid #f97316; background:#111827;}"
            "QPushButton{background:#1e293b; color:#f8fafc; border:1px solid #334155; border-radius:8px; padding:7px 12px;}"
            "QPushButton:hover{background:#334155;}"
            "QTableWidget{background:#111827; alternate-background-color:#0f172a; color:#e5e7eb; border:1px solid #334155; gridline-color:#334155;}"
            "QTableWidget::item{padding:6px 8px;}"
            "QTableWidget::item:selected{background:#7db7ff; color:#ffffff;}"
            "QTableWidget::item:hover{background:#20364f;}"
            "QTableWidget::item:focus{border:1px solid #f97316;}"
            "QTableWidget::item:selected:focus{border:1px solid #f97316;}"
            "QHeaderView::section{background:#1f2937; color:#e5e7eb; padding:8px 6px;}"
        )

        self.search_input.setFocus()

    def _accept_row(self, row: int):
        table = getattr(self, "table", None)
        if table is None:
            return
        if row < 0 or row >= table.rowCount():
            return
        table.setCurrentCell(row, 0)
        table.selectRow(row)
        self._accept_selected()

    def _accept_current_row(self):
        table = getattr(self, "table", None)
        if table is None:
            return
        row = table.currentRow()
        if row < 0 and table.rowCount() > 0:
            row = 0
        self._accept_row(row)

    def keyPressEvent(self, event):
        search_input = getattr(self, "search_input", None)
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self._accept_current_row()
            return
        if event.key() == Qt.Key_Escape:
            if search_input is not None and search_input.text().strip():
                search_input.clear()
            else:
                self.reject()
            return
        super().keyPressEvent(event)

    def eventFilter(self, watched, event):
        search_input = getattr(self, "search_input", None)
        table = getattr(self, "table", None)

        if watched is search_input and event.type() == QEvent.KeyPress and event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self._accept_current_row()
            return True
        if watched is search_input and event.type() == QEvent.KeyPress and event.key() == Qt.Key_Escape:
            if search_input is not None and search_input.text().strip():
                search_input.clear()
            else:
                self.reject()
            return True
        if watched is table and event.type() == QEvent.KeyPress and event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self._accept_current_row()
            return True
        if watched is table and event.type() == QEvent.KeyPress and event.key() == Qt.Key_Escape:
            self.reject()
            return True
        return super().eventFilter(watched, event)