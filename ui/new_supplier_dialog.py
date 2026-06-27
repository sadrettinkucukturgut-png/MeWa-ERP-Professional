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
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from models.supplier_model import SupplierModel


class NewSupplierDialog(QDialog):
    def __init__(self, supplier_code: str | None = None, parent=None):
        super().__init__(parent)
        self.supplier_code = supplier_code
        self.is_edit_mode = supplier_code is not None
        self.setWindowTitle("Tedarikçi Düzenle" if self.is_edit_mode else "Yeni Tedarikçi")
        self.resize(900, 760)
        self._setup_ui()

        if self.is_edit_mode:
            self._load_supplier_data()

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
        content_layout.setSpacing(12)

        title = QLabel("🏭 Tedarikçi Kartı")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        content_layout.addWidget(title)

        form_layout = QFormLayout()
        form_layout.setLabelAlignment(Qt.AlignLeft)
        form_layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)

        self.supplier_code_input = QLineEdit()
        self.company_name_input = QLineEdit()
        self.contact_person_input = QLineEdit()
        self.phone_input = QLineEdit()
        self.whatsapp_input = QLineEdit()
        self.email_input = QLineEdit()
        self.website_input = QLineEdit()
        self.tax_office_input = QLineEdit()
        self.tax_number_input = QLineEdit()
        self.country_input = QLineEdit()
        self.city_input = QLineEdit()
        self.district_input = QLineEdit()
        self.address_input = QTextEdit()
        self.address_input.setFixedHeight(90)
        self.default_currency_input = QComboBox()
        self.default_currency_input.addItems(["USD", "EUR", "TRY", "AED", "SAR", "GBP", "CNY", "RUB"])
        self.default_currency_input.setCurrentText("USD")
        self.payment_term_input = QLineEdit()
        self.bank_name_input = QLineEdit()
        self.iban_input = QLineEdit()
        self.swift_code_input = QLineEdit()
        self.notes_input = QTextEdit()
        self.notes_input.setFixedHeight(90)

        fields = [
            ("Tedarikçi Kodu*", self.supplier_code_input),
            ("Firma Ünvanı*", self.company_name_input),
            ("Yetkili Kişi*", self.contact_person_input),
            ("Telefon", self.phone_input),
            ("WhatsApp", self.whatsapp_input),
            ("E-Posta", self.email_input),
            ("Website", self.website_input),
            ("Vergi Dairesi", self.tax_office_input),
            ("Vergi No", self.tax_number_input),
            ("Ülke", self.country_input),
            ("Şehir", self.city_input),
            ("İlçe", self.district_input),
            ("Adres", self.address_input),
            ("Varsayılan Para Birimi", self.default_currency_input),
            ("Ödeme Vadesi", self.payment_term_input),
            ("Banka Adı", self.bank_name_input),
            ("IBAN", self.iban_input),
            ("SWIFT", self.swift_code_input),
            ("Notlar", self.notes_input),
        ]

        for label, widget in fields:
            form_layout.addRow(label, widget)

        content_layout.addLayout(form_layout)

        if self.is_edit_mode:
            self.supplier_code_input.setEnabled(False)

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

    def _load_supplier_data(self):
        supplier = SupplierModel.getir(self.supplier_code)
        if not supplier:
            QMessageBox.warning(self, "Bilgi", "Tedarikçi bulunamadı.")
            self.reject()
            return

        self.supplier_code_input.setText(supplier.get("supplier_code") or "")
        self.company_name_input.setText(supplier.get("company_name") or "")
        self.contact_person_input.setText(supplier.get("contact_person") or "")
        self.phone_input.setText(supplier.get("phone") or "")
        self.whatsapp_input.setText(supplier.get("whatsapp") or "")
        self.email_input.setText(supplier.get("email") or "")
        self.website_input.setText(supplier.get("website") or "")
        self.tax_office_input.setText(supplier.get("tax_office") or "")
        self.tax_number_input.setText(supplier.get("tax_number") or "")
        self.country_input.setText(supplier.get("country") or "")
        self.city_input.setText(supplier.get("city") or "")
        self.district_input.setText(supplier.get("district") or "")
        self.address_input.setPlainText(supplier.get("address") or "")
        self.default_currency_input.setCurrentText(supplier.get("default_currency") or "USD")
        self.payment_term_input.setText(supplier.get("payment_term") or "")
        self.bank_name_input.setText(supplier.get("bank_name") or "")
        self.iban_input.setText(supplier.get("iban") or "")
        self.swift_code_input.setText(supplier.get("swift_code") or "")
        self.notes_input.setPlainText(supplier.get("notes") or "")

    def _on_save(self):
        supplier_code = self.supplier_code_input.text().strip()
        company_name = self.company_name_input.text().strip()
        contact_person = self.contact_person_input.text().strip()

        if not supplier_code or not company_name or not contact_person:
            QMessageBox.warning(self, "Uyarı", "Tedarikçi kodu, firma ünvanı ve yetkili kişi zorunludur.")
            return

        if SupplierModel.supplier_code_exists(supplier_code, self.supplier_code):
            QMessageBox.warning(self, "Uyarı", "Bu tedarikçi kodu zaten kullanılıyor.")
            return

        try:
            if self.is_edit_mode:
                SupplierModel.guncelle(
                    self.supplier_code,
                    supplier_code,
                    company_name,
                    contact_person,
                    self.phone_input.text().strip(),
                    self.whatsapp_input.text().strip(),
                    self.email_input.text().strip(),
                    self.website_input.text().strip(),
                    self.tax_office_input.text().strip(),
                    self.tax_number_input.text().strip(),
                    self.country_input.text().strip(),
                    self.city_input.text().strip(),
                    self.district_input.text().strip(),
                    self.address_input.toPlainText().strip(),
                    self.default_currency_input.currentText(),
                    self.payment_term_input.text().strip(),
                    self.bank_name_input.text().strip(),
                    self.iban_input.text().strip(),
                    self.swift_code_input.text().strip(),
                    self.notes_input.toPlainText().strip(),
                )
                QMessageBox.information(self, "Başarılı", "Tedarikçi başarıyla güncellendi.")
            else:
                SupplierModel.ekle(
                    supplier_code,
                    company_name,
                    contact_person,
                    self.phone_input.text().strip(),
                    self.whatsapp_input.text().strip(),
                    self.email_input.text().strip(),
                    self.website_input.text().strip(),
                    self.tax_office_input.text().strip(),
                    self.tax_number_input.text().strip(),
                    self.country_input.text().strip(),
                    self.city_input.text().strip(),
                    self.district_input.text().strip(),
                    self.address_input.toPlainText().strip(),
                    self.default_currency_input.currentText(),
                    self.payment_term_input.text().strip(),
                    self.bank_name_input.text().strip(),
                    self.iban_input.text().strip(),
                    self.swift_code_input.text().strip(),
                    self.notes_input.toPlainText().strip(),
                )
                QMessageBox.information(self, "Başarılı", "Tedarikçi başarıyla eklendi.")
            self.accept()
        except Exception as exc:
            QMessageBox.critical(self, "Hata", f"Tedarikçi kaydedilirken bir hata oluştu:\n{exc}")
