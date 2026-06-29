from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QLabel, QWidget


class BaseDocumentTotals(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setHorizontalSpacing(10)
        layout.setVerticalSpacing(6)

        self.subtotal_value = QLabel("0.00")
        self.discount_value = QLabel("0.00")
        self.vat_value = QLabel("0.00")
        self.grand_total_value = QLabel("0.00")

        for value in (self.subtotal_value, self.discount_value, self.vat_value, self.grand_total_value):
            value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            value.setStyleSheet("font-size:14px; font-weight:700;")

        layout.addWidget(QLabel("Ara Toplam"), 0, 0)
        layout.addWidget(self.subtotal_value, 0, 1)
        layout.addWidget(QLabel("İskonto"), 1, 0)
        layout.addWidget(self.discount_value, 1, 1)
        layout.addWidget(QLabel("KDV"), 2, 0)
        layout.addWidget(self.vat_value, 2, 1)
        layout.addWidget(QLabel("Genel Toplam"), 3, 0)
        layout.addWidget(self.grand_total_value, 3, 1)

    def set_values(self, subtotal: float, discount: float, vat: float, grand_total: float) -> None:
        self.subtotal_value.setText(f"{subtotal:,.2f}")
        self.discount_value.setText(f"{discount:,.2f}")
        self.vat_value.setText(f"{vat:,.2f}")
        self.grand_total_value.setText(f"{grand_total:,.2f}")
