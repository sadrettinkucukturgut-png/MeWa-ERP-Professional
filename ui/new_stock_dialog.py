from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from models.stock_model import StockModel


class NewStockDialog(QDialog):
    def __init__(self, stock_code: str | None = None):
        super().__init__()
        self.stock_code = stock_code
        self.setWindowTitle("Yeni Stok Kartı" if stock_code is None else "Stok Kartı Düzenle")
        self.resize(760, 640)
        self._setup_ui()

        if stock_code:
            self._load_stock_data()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        title = QLabel("📦 Stok Kartı")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        layout.addWidget(title)

        form_layout = QFormLayout()
        form_layout.setLabelAlignment(Qt.AlignLeft)
        form_layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)

        self.stock_code_input = QLineEdit()
        self.barcode_input = QLineEdit()
        self.product_name_input = QLineEdit()
        self.category_input = QLineEdit()
        self.brand_input = QLineEdit()
        self.unit_input = QLineEdit()
        self.purchase_price_input = QLineEdit()
        self.purchase_currency_input = QComboBox()
        self.purchase_currency_input.addItems(["USD", "EUR", "TRY", "AED", "SAR", "GBP", "CNY", "RUB"])
        self.purchase_currency_input.setCurrentText("USD")
        self.sale_price_input = QLineEdit()
        self.sale_currency_input = QComboBox()
        self.sale_currency_input.addItems(["USD", "EUR", "TRY", "AED", "SAR", "GBP", "CNY", "RUB"])
        self.sale_currency_input.setCurrentText("USD")
        self.vat_rate_input = QLineEdit()
        self.critical_stock_input = QLineEdit()
        self.current_stock_input = QLineEdit()
        self.warehouse_input = QLineEdit()
        self.shelf_input = QLineEdit()
        self.origin_input = QLineEdit()
        self.description_input = QTextEdit()
        self.description_input.setFixedHeight(90)

        purchase_widget = QWidget()
        purchase_row = QHBoxLayout(purchase_widget)
        purchase_row.setContentsMargins(0, 0, 0, 0)
        purchase_row.setSpacing(8)
        purchase_row.addWidget(self.purchase_price_input, 1)
        purchase_row.addWidget(self.purchase_currency_input, 0)

        sale_widget = QWidget()
        sale_row = QHBoxLayout(sale_widget)
        sale_row.setContentsMargins(0, 0, 0, 0)
        sale_row.setSpacing(8)
        sale_row.addWidget(self.sale_price_input, 1)
        sale_row.addWidget(self.sale_currency_input, 0)

        fields = [
            ("Stok Kodu*", self.stock_code_input),
            ("Barkod", self.barcode_input),
            ("Ürün Adı*", self.product_name_input),
            ("Kategori", self.category_input),
            ("Marka", self.brand_input),
            ("Birim", self.unit_input),
            ("Alış Fiyatı", purchase_widget),
            ("Satış Fiyatı", sale_widget),
            ("KDV Oranı", self.vat_rate_input),
            ("Kritik Stok", self.critical_stock_input),
            ("Mevcut Stok", self.current_stock_input),
            ("Depo", self.warehouse_input),
            ("Raf", self.shelf_input),
            ("Menşei", self.origin_input),
            ("Açıklama", self.description_input),
        ]

        for label, widget in fields:
            form_layout.addRow(label, widget)

        layout.addLayout(form_layout)

        if self.stock_code:
            self.stock_code_input.setEnabled(False)

        button_row = QHBoxLayout()
        button_row.addStretch()

        save_button = QPushButton("Kaydet")
        save_button.clicked.connect(self._on_save)
        save_button.setDefault(True)
        cancel_button = QPushButton("İptal")
        cancel_button.clicked.connect(self.reject)

        button_row.addWidget(save_button)
        button_row.addWidget(cancel_button)
        layout.addLayout(button_row)

    def _load_stock_data(self):
        stok = StockModel.getir(self.stock_code)
        if not stok:
            return

        self.stock_code_input.setText(stok[0] or "")
        self.barcode_input.setText(stok[1] or "")
        self.product_name_input.setText(stok[2] or "")
        self.category_input.setText(stok[3] or "")
        self.brand_input.setText(stok[4] or "")
        self.unit_input.setText(stok[5] or "")
        self.purchase_price_input.setText(str(stok[6] or ""))
        self.purchase_currency_input.setCurrentText(stok[7] or "USD")
        self.sale_price_input.setText(str(stok[8] or ""))
        self.sale_currency_input.setCurrentText(stok[9] or "USD")
        self.vat_rate_input.setText(str(stok[10] or ""))
        self.critical_stock_input.setText(str(stok[11] or ""))
        self.current_stock_input.setText(str(stok[12] or ""))
        self.warehouse_input.setText(stok[13] or "")
        self.shelf_input.setText(stok[14] or "")
        self.origin_input.setText(stok[15] or "")
        self.description_input.setPlainText(stok[16] or "")

    def _on_save(self):
        stock_code = self.stock_code_input.text().strip()
        product_name = self.product_name_input.text().strip()

        if not stock_code or not product_name:
            QMessageBox.warning(self, "Uyarı", "Stok kodu ve ürün adı zorunludur.")
            return

        try:
            if self.stock_code:
                StockModel.guncelle(
                    self.stock_code,
                    self.barcode_input.text().strip(),
                    product_name,
                    self.category_input.text().strip(),
                    self.brand_input.text().strip(),
                    self.unit_input.text().strip(),
                    self.purchase_price_input.text().strip(),
                    self.purchase_currency_input.currentText(),
                    self.sale_price_input.text().strip(),
                    self.sale_currency_input.currentText(),
                    self.vat_rate_input.text().strip(),
                    self.critical_stock_input.text().strip(),
                    self.current_stock_input.text().strip(),
                    self.warehouse_input.text().strip(),
                    self.shelf_input.text().strip(),
                    self.origin_input.text().strip(),
                    self.description_input.toPlainText().strip(),
                )
            else:
                StockModel.ekle(
                    stock_code,
                    self.barcode_input.text().strip(),
                    product_name,
                    self.category_input.text().strip(),
                    self.brand_input.text().strip(),
                    self.unit_input.text().strip(),
                    self.purchase_price_input.text().strip(),
                    self.purchase_currency_input.currentText(),
                    self.sale_price_input.text().strip(),
                    self.sale_currency_input.currentText(),
                    self.vat_rate_input.text().strip(),
                    self.critical_stock_input.text().strip(),
                    self.current_stock_input.text().strip(),
                    self.warehouse_input.text().strip(),
                    self.shelf_input.text().strip(),
                    self.origin_input.text().strip(),
                    self.description_input.toPlainText().strip(),
                )

            QMessageBox.information(self, "Başarılı", "Stok kartı kaydedildi.")
            self.accept()
        except Exception as exc:
            QMessageBox.critical(self, "Hata", f"Stok kaydedilirken bir hata oluştu:\n{exc}")
