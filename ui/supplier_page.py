from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ui.new_supplier_dialog import NewSupplierDialog
from ui.supplier_list_page import SupplierListPage


class SupplierPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        title = QLabel("🏭 Tedarikçi Yönetimi")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size:26px; font-weight:bold; color:white; padding:15px;")
        layout.addWidget(title)

        toolbar_layout = QHBoxLayout()
        self.btn_new = QPushButton("➕ Yeni Tedarikçi")
        self.btn_list = QPushButton("📋 Tedarikçi Listesi")
        for button in [self.btn_new, self.btn_list]:
            button.setMinimumHeight(40)
            toolbar_layout.addWidget(button)
        layout.addLayout(toolbar_layout)

        info_label = QLabel("Tedarikçi modülü hazır.")
        info_label.setAlignment(Qt.AlignCenter)
        info_label.setStyleSheet("font-size:18px; color:gray;")
        layout.addStretch()
        layout.addWidget(info_label)
        layout.addStretch()

        self.btn_new.clicked.connect(self.new_supplier)
        self.btn_list.clicked.connect(self.open_supplier_list)

    def new_supplier(self):
        dialog = NewSupplierDialog()
        dialog.exec()

    def open_supplier_list(self):
        self.dialog = SupplierListPage()
        self.dialog.show()
