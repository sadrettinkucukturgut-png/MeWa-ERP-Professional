from __future__ import annotations

from PySide6.QtWidgets import QHeaderView, QTableWidget


class BaseDocumentTable(QTableWidget):
    def apply_document_defaults(self) -> None:
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QTableWidget.SelectRows)
        self.setSelectionMode(QTableWidget.SingleSelection)
        self.setSortingEnabled(False)
        self.verticalHeader().setVisible(False)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.horizontalHeader().setStretchLastSection(False)
