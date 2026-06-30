from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt, QSettings
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
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

from services.document_export_service import DocumentExportService
from shared.widgets.table_column_state import add_layout_lock_toggle, apply_table_column_standard
from shared.widgets.table_visual import apply_list_table_visuals, create_record_count_label, set_record_count


class FinanceBasePage(QWidget):
    def __init__(
        self,
        *,
        title: str,
        layout_key: str,
        column_labels: list[str],
        stat_titles: list[str],
    ):
        super().__init__()
        self.page_title_text = title
        self.layout_key = layout_key
        self.column_labels = column_labels
        self.stat_titles = stat_titles

        self.settings = QSettings("MeWa", "ERP")
        self.export_service = DocumentExportService(self)

        self._setup_ui()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        title = QLabel(self.page_title_text)
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size:24px; font-weight:bold; padding:8px 0; color:#e2e8f0;")
        root.addWidget(title)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search")
        self.search_input.textChanged.connect(self._on_search_changed)
        root.addWidget(self.search_input)

        self.toolbar = QToolBar()
        self.toolbar.setMovable(False)
        root.addWidget(self.toolbar)

        self.action_new = QAction("New", self)
        self.action_edit = QAction("Edit", self)
        self.action_delete = QAction("Delete", self)
        self.action_refresh = QAction("Refresh", self)
        self.action_search = QAction("Search", self)
        self.action_print = QAction("Print", self)
        self.action_pdf = QAction("Save PDF", self)
        self.action_excel = QAction("Export Excel", self)
        self.action_share = QAction("Share", self)
        self.action_columns = QAction("Column Visibility", self)

        for action in [
            self.action_new,
            self.action_edit,
            self.action_delete,
            self.action_refresh,
            self.action_search,
            self.action_print,
            self.action_pdf,
            self.action_excel,
            self.action_share,
            self.action_columns,
        ]:
            self.toolbar.addAction(action)

        self._build_stats(root)

        self.table = QTableWidget()
        self.table.setColumnCount(len(self.column_labels))
        self.table.setHorizontalHeaderLabels(self.column_labels)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        self.table.verticalHeader().setVisible(False)
        self.table.doubleClicked.connect(self._on_edit)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        apply_list_table_visuals(self.table)
        apply_table_column_standard(self.table, self.settings, self.layout_key, keep_last_column_stretch=False)
        self.action_layout_lock = add_layout_lock_toggle(
            self.toolbar,
            self.table,
            self.settings,
            self.layout_key,
            self,
            keep_last_column_stretch=False,
        )
        root.addWidget(self.table)

        self.record_count_label = create_record_count_label()
        self.record_count_label.setStyleSheet("font-size: 12px; color: #94a3b8; padding: 4px 2px;")
        root.addWidget(self.record_count_label, alignment=Qt.AlignRight)

        self.setStyleSheet(
            "QWidget{background:#0b1220;}"
            "QLineEdit{background:#0f172a; color:#e2e8f0; border:1px solid #334155; border-radius:8px; padding:8px;}"
            "QToolBar{background:#111827; border:1px solid #334155; border-radius:8px; spacing:6px; padding:6px;}"
        )

        self.action_new.triggered.connect(self._on_new)
        self.action_edit.triggered.connect(self._on_edit)
        self.action_delete.triggered.connect(self._on_delete)
        self.action_refresh.triggered.connect(self.load_data)
        self.action_search.triggered.connect(lambda: self.load_data(self.search_input.text()))
        self.action_print.triggered.connect(self._export_print)
        self.action_pdf.triggered.connect(self._export_pdf)
        self.action_excel.triggered.connect(self._export_excel)
        self.action_share.triggered.connect(self._share_default)
        self.action_columns.triggered.connect(self._show_column_menu)

    def _build_stats(self, root_layout: QVBoxLayout):
        self.stat_labels: dict[str, QLabel] = {}
        stat_row = QToolBar()
        stat_row.setMovable(False)
        stat_row.setStyleSheet("QToolBar{background:#0f172a; border:1px solid #334155; border-radius:12px; padding:8px;}")

        for title in self.stat_titles:
            card = QWidget()
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(12, 8, 12, 8)
            value = QLabel("0")
            value.setStyleSheet("font-size:20px; font-weight:700; color:#f8fafc;")
            label = QLabel(title)
            label.setStyleSheet("font-size:12px; color:#94a3b8;")
            card_layout.addWidget(value)
            card_layout.addWidget(label)
            stat_row.addWidget(card)
            self.stat_labels[title] = value

        root_layout.addWidget(stat_row)

    def set_stats(self, values: dict[str, str]):
        for key, lbl in self.stat_labels.items():
            lbl.setText(str(values.get(key, "0")))

    def set_table_rows(self, rows: list[list[str]]):
        sorting = self.table.isSortingEnabled()
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(rows))
        for r, row_values in enumerate(rows):
            for c, val in enumerate(row_values):
                self.table.setItem(r, c, QTableWidgetItem(str(val)))
        self.table.setSortingEnabled(sorting)
        set_record_count(self.record_count_label, len(rows))

    def selected_row_data(self) -> dict:
        row = self.table.currentRow()
        if row < 0:
            return {}
        data = {}
        for c, col in enumerate(self.column_labels):
            item = self.table.item(row, c)
            data[col] = "" if item is None else item.text()
        return data

    def payload_provider(self) -> dict:
        headers = self.column_labels
        rows: list[list[str]] = []
        for r in range(self.table.rowCount()):
            row_values = []
            for c in range(self.table.columnCount()):
                item = self.table.item(r, c)
                row_values.append("" if item is None else item.text())
            rows.append(row_values)
        return {
            "title": self.page_title_text,
            "filename_base": self.layout_key,
            "headers": headers,
            "rows": rows,
            "document_number": "",
            "currency": "USD",
            "customer_name": "",
            "customer_code": "",
        }

    def _export_excel(self):
        self.export_service.export_excel(self._doc_payload())

    def _export_pdf(self):
        self.export_service.export_pdf(self._doc_payload())

    def _export_print(self):
        self.export_service.print_document(self._doc_payload())

    def _share_default(self):
        self.export_service.share_document(self._doc_payload())

    def _doc_payload(self):
        data = self.payload_provider()
        return self.export_service.table_payload(
            title=str(data.get("title") or self.page_title_text),
            filename_base=str(data.get("filename_base") or self.layout_key),
            headers=list(data.get("headers") or []),
            rows=[list(r) for r in (data.get("rows") or [])],
            document_number=str(data.get("document_number") or ""),
            currency=str(data.get("currency") or "USD"),
            customer_name=str(data.get("customer_name") or ""),
            customer_code=str(data.get("customer_code") or ""),
        )

    def _on_search_changed(self, text: str):
        self.load_data(text)

    def _show_column_menu(self):
        menu = QMenu(self)
        for index, label in enumerate(self.column_labels):
            action = QAction(label, self)
            action.setCheckable(True)
            action.setChecked(not self.table.isColumnHidden(index))
            action.triggered.connect(lambda checked, col=index: self.table.setColumnHidden(col, not checked))
            menu.addAction(action)
        menu.exec_(self.toolbar.mapToGlobal(self.toolbar.rect().bottomLeft()))

    def _show_context_menu(self, pos):
        row = self.table.rowAt(pos.y())
        if row >= 0:
            self.table.selectRow(row)
        menu = QMenu(self)
        edit_action = QAction("Edit", self)
        delete_action = QAction("Delete", self)
        edit_action.triggered.connect(self._on_edit)
        delete_action.triggered.connect(self._on_delete)
        menu.addAction(edit_action)
        menu.addAction(delete_action)
        menu.exec_(self.table.viewport().mapToGlobal(pos))

    def _on_new(self):
        QMessageBox.information(self, "Info", "Not implemented.")

    def _on_edit(self):
        QMessageBox.information(self, "Info", "Not implemented.")

    def _on_delete(self):
        QMessageBox.information(self, "Info", "Not implemented.")

    def load_data(self, keyword: str = ""):
        pass
