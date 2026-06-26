from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from models.stock_model import StockModel


class StockReferenceDialog(QDialog):
    def __init__(self, title: str, reference_type: str):
        super().__init__()
        self.reference_type = reference_type
        self.setWindowTitle(title)
        self.resize(360, 320)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        label = QLabel(f"{self.reference_type.title()} ekle veya seç")
        layout.addWidget(label)

        self.input = QLineEdit()
        self.input.setPlaceholderText("Yeni değer girin")
        layout.addWidget(self.input)

        self.list_widget = QListWidget()
        self._load_items()
        layout.addWidget(self.list_widget)

        buttons = QHBoxLayout()
        add_button = QPushButton("Ekle")
        add_button.clicked.connect(self._add_item)
        close_button = QPushButton("Kapat")
        close_button.clicked.connect(self.accept)
        buttons.addWidget(add_button)
        buttons.addStretch()
        buttons.addWidget(close_button)
        layout.addLayout(buttons)

    def _load_items(self):
        if self.reference_type == "category":
            values = StockModel.get_categories()
        elif self.reference_type == "brand":
            values = StockModel.get_brands()
        else:
            values = StockModel.get_warehouses()

        self.list_widget.clear()
        self.list_widget.addItems(values)

    def _add_item(self):
        value = self.input.text().strip()
        if not value:
            QMessageBox.warning(self, "Uyarı", "Lütfen bir değer girin.")
            return

        if self.reference_type == "category":
            StockModel.add_category(value)
        elif self.reference_type == "brand":
            StockModel.add_brand(value)
        else:
            StockModel.add_warehouse(value)

        self.input.clear()
        self._load_items()
        QMessageBox.information(self, "Başarılı", "Değer eklendi.")
