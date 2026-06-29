from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from models.stock_model import StockModel
from ui.stock_reference_dialog import StockReferenceDialog


class NewStockDialog(QDialog):
    def __init__(self, stock_code: str | None = None):
        super().__init__()
        self.stock_code = stock_code
        self.image_path = ""
        self.setWindowTitle("Yeni Stok Kartı" if stock_code is None else "Stok Kartı Düzenle")
        self.resize(840, 760)
        self._setup_ui()

        if stock_code:
            self._load_stock_data()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setFrameShape(QScrollArea.NoFrame)

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(20, 20, 20, 20)
        content_layout.setSpacing(14)

        title = QLabel("📦 Stok Kartı")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        content_layout.addWidget(title)

        form_layout = QFormLayout()
        form_layout.setLabelAlignment(Qt.AlignLeft)
        form_layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)

        self.stock_code_input = QLineEdit()
        self.barcode_input = QLineEdit()
        self.product_name_input = QLineEdit()

        self.category_combo = QComboBox()
        self.category_combo.setEditable(True)
        self.category_combo.setInsertPolicy(QComboBox.NoInsert)
        self.brand_combo = QComboBox()
        self.brand_combo.setEditable(True)
        self.brand_combo.setInsertPolicy(QComboBox.NoInsert)
        self.hs_code_input = QLineEdit()
        self.hs_code_input.setMaxLength(20)
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
        self.weight_input = QDoubleSpinBox()
        self.weight_input.setDecimals(3)
        self.weight_input.setMinimum(0.0)
        self.weight_input.setMaximum(999999.999)
        self.weight_input.setSingleStep(0.001)
        self.shelf_input = QLineEdit()
        self.origin_input = QLineEdit()

        self.image_label = QLabel("Görsel yok")
        self.image_label.setFixedSize(120, 120)
        self.image_label.setStyleSheet("border:1px solid #cbd5e1; border-radius:8px; background:#f8fafc;")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_button = QPushButton("Görsel Seç")
        self.image_button.clicked.connect(self._select_image)
        self.clear_image_button = QPushButton("Temizle")
        self.clear_image_button.clicked.connect(self._clear_image)

        image_widget = QWidget()
        image_layout = QHBoxLayout(image_widget)
        image_layout.setContentsMargins(0, 0, 0, 0)
        image_layout.setSpacing(8)
        image_layout.addWidget(self.image_label)
        image_layout.addWidget(self.image_button)
        image_layout.addWidget(self.clear_image_button)

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

        category_widget = self._build_reference_widget(self.category_combo, "Kategori")
        brand_widget = self._build_reference_widget(self.brand_combo, "Marka")

        fields = [
            ("Stok Kodu*", self.stock_code_input),
            ("Barkod", self.barcode_input),
            ("Ürün Adı*", self.product_name_input),
            ("Kategori", category_widget),
            ("HS Code", self.hs_code_input),
            ("Marka", brand_widget),
            ("Birim", self.unit_input),
            ("Alış Fiyatı", purchase_widget),
            ("Satış Fiyatı", sale_widget),
            ("KDV Oranı", self.vat_rate_input),
            ("Weight (KG)", self.weight_input),
            ("Raf", self.shelf_input),
            ("Menşei", self.origin_input),
            ("Ürün Görseli", image_widget),
        ]

        for label, widget in fields:
            form_layout.addRow(label, widget)

        content_layout.addLayout(form_layout)

        self._load_reference_values()

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
        content_layout.addLayout(button_row)

        scroll_area.setWidget(content_widget)
        layout.addWidget(scroll_area)

    def _build_reference_widget(self, combo, title):
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(combo, 1)
        button = QPushButton("...")
        button.clicked.connect(lambda checked=False, target=combo, label=title: self._manage_reference(target, label))
        layout.addWidget(button)
        return widget

    def _load_reference_values(self):
        self.category_combo.clear()
        self.category_combo.addItems(StockModel.get_categories())
        self.brand_combo.clear()
        self.brand_combo.addItems(StockModel.get_brands())

    def _manage_reference(self, combo, title):
        if title == "Kategori":
            dialog = StockReferenceDialog("Kategori Yönetimi", "category")
        else:
            dialog = StockReferenceDialog("Marka Yönetimi", "brand")

        if dialog.exec():
            self._load_reference_values()
            current_text = combo.currentText()
            if current_text:
                index = combo.findText(current_text)
                if index >= 0:
                    combo.setCurrentIndex(index)

    def _select_image(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Ürün Görseli Seç", "", "Resim Dosyaları (*.png *.jpg *.jpeg *.bmp *.gif)")
        if file_path:
            self.image_path = file_path
            pixmap = QPixmap(file_path)
            if not pixmap.isNull():
                self.image_label.setPixmap(pixmap.scaled(120, 120, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            else:
                self.image_label.setText("Görsel yüklenemedi")

    def _clear_image(self):
        self.image_path = ""
        self.image_label.clear()
        self.image_label.setText("Görsel yok")

    def _load_stock_data(self):
        stok = StockModel.getir(self.stock_code)
        if not stok:
            return

        self.stock_code_input.setText(stok[0] or "")
        self.barcode_input.setText(stok[1] or "")
        self.product_name_input.setText(stok[2] or "")
        self._set_combo_value(self.category_combo, stok[3])
        self.hs_code_input.setText(stok[4] or "")
        self._set_combo_value(self.brand_combo, stok[5])
        self.unit_input.setText(stok[6] or "")
        self.purchase_price_input.setText(str(stok[7] or ""))
        self.purchase_currency_input.setCurrentText(stok[8] or "USD")
        self.sale_price_input.setText(str(stok[9] or ""))
        self.sale_currency_input.setCurrentText(stok[10] or "USD")
        self.vat_rate_input.setText(str(stok[11] or ""))
        self.weight_input.setValue(float(stok[12] or 0))
        self.shelf_input.setText(stok[14] or "")
        self.origin_input.setText(stok[15] or "")
        self.image_path = stok[17] or ""
        if self.image_path:
            pixmap = QPixmap(self.image_path)
            if not pixmap.isNull():
                self.image_label.setPixmap(pixmap.scaled(120, 120, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            else:
                self.image_label.setText("Görsel yüklenemedi")
        else:
            self._clear_image()

    def _set_combo_value(self, combo, value):
        if not value:
            combo.setCurrentText("")
            return
        index = combo.findText(value)
        if index >= 0:
            combo.setCurrentIndex(index)
        else:
            combo.addItem(value)
            combo.setCurrentText(value)

    def _on_save(self):
        stock_code = self.stock_code_input.text().strip()
        product_name = self.product_name_input.text().strip()
        barcode = self.barcode_input.text().strip()

        if not stock_code or not product_name:
            QMessageBox.warning(self, "Uyarı", "Stok kodu ve ürün adı zorunludur.")
            return

        if barcode and StockModel.barcode_exists(barcode, self.stock_code):
            QMessageBox.warning(self, "Uyarı", "Bu barkod başka bir stok kartında kullanılıyor.")
            return

        hs_code = self.hs_code_input.text().strip()
        if hs_code and (len(hs_code) > 20 or any(ch not in "0123456789." for ch in hs_code)):
            QMessageBox.warning(self, "Uyarı", "HS Code en fazla 20 karakter olmalı ve sadece rakam ile nokta içermelidir.")
            return

        if self.weight_input.value() < 0:
            QMessageBox.warning(self, "Uyarı", "Weight (KG) negatif olamaz.")
            return

        current_stock_value = "0"
        if self.stock_code:
            mevcut = StockModel.getir(self.stock_code)
            if mevcut:
                current_stock_value = str(mevcut[13] or 0)

        try:
            if self.stock_code:
                StockModel.guncelle(
                    self.stock_code,
                    barcode,
                    product_name,
                    self.category_combo.currentText().strip(),
                    hs_code,
                    self.brand_combo.currentText().strip(),
                    self.unit_input.text().strip(),
                    self.purchase_price_input.text().strip(),
                    self.purchase_currency_input.currentText(),
                    self.sale_price_input.text().strip(),
                    self.sale_currency_input.currentText(),
                    self.vat_rate_input.text().strip(),
                    f"{self.weight_input.value():.3f}",
                    current_stock_value,
                    self.shelf_input.text().strip(),
                    self.origin_input.text().strip(),
                    "",
                    self.image_path,
                )
            else:
                StockModel.ekle(
                    stock_code,
                    barcode,
                    product_name,
                    self.category_combo.currentText().strip(),
                    hs_code,
                    self.brand_combo.currentText().strip(),
                    self.unit_input.text().strip(),
                    self.purchase_price_input.text().strip(),
                    self.purchase_currency_input.currentText(),
                    self.sale_price_input.text().strip(),
                    self.sale_currency_input.currentText(),
                    self.vat_rate_input.text().strip(),
                    f"{self.weight_input.value():.3f}",
                    current_stock_value,
                    self.shelf_input.text().strip(),
                    self.origin_input.text().strip(),
                    "",
                    self.image_path,
                )

            QMessageBox.information(self, "Başarılı", "Stok kartı kaydedildi.")
            self.accept()
        except Exception as exc:
            QMessageBox.critical(self, "Hata", f"Stok kaydedilirken bir hata oluştu:\n{exc}")
