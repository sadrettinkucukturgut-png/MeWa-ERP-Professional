from __future__ import annotations

from typing import List

from PySide6.QtWidgets import QTableWidget, QWidget


class BaseDocumentPage(QWidget):
    """Shared helpers for scalable document list pages."""

    @staticmethod
    def table_headers(table: QTableWidget) -> List[str]:
        headers: List[str] = []
        for col in range(table.columnCount()):
            item = table.horizontalHeaderItem(col)
            headers.append("" if item is None else item.text())
        return headers

    @staticmethod
    def table_rows(table: QTableWidget) -> List[List[str]]:
        rows: List[List[str]] = []
        for row in range(table.rowCount()):
            values: List[str] = []
            for col in range(table.columnCount()):
                item = table.item(row, col)
                values.append("" if item is None else item.text())
            rows.append(values)
        return rows
