from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ui.new_stock_dialog import NewStockDialog
from ui.stock_list_page import StockListPage


class StockPage(QWidget):
    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        title = QLabel("📦 Stok Yönetimi")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 24px; font-weight: bold; padding: 10px 0;")
        layout.addWidget(title)

        button_row = QHBoxLayout()
        self.btn_yeni = QPushButton("➕ Yeni Stok")
        self.btn_liste = QPushButton("📋 Stok Listesi")

        for button in [self.btn_yeni, self.btn_liste]:
            button.setMinimumHeight(40)
            button_row.addWidget(button)

        layout.addLayout(button_row)
        layout.addStretch()

        self.btn_yeni.clicked.connect(self.yeni_stok)
        self.btn_liste.clicked.connect(self.stok_listesi)

    def yeni_stok(self):
        dialog = NewStockDialog()
        dialog.exec()

    def stok_listesi(self):
        self.dialog = StockListPage()
        self.dialog.show()
