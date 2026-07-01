from __future__ import annotations

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)


class CashAccountDialog(QDialog):
    def __init__(self, parent=None, data: dict | None = None):
        super().__init__(parent)
        self.setWindowTitle("Kasa Hesabı")
        self.resize(520, 320)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.code_input = QLineEdit()
        self.name_input = QLineEdit()
        self.currency_combo = QComboBox()
        self.currency_combo.addItems(["TRY", "USD", "EUR"])
        self.opening_balance = QDoubleSpinBox()
        self.opening_balance.setDecimals(2)
        self.opening_balance.setMaximum(999999999)
        self.opening_date = QDateEdit()
        self.opening_date.setCalendarPopup(True)
        self.opening_date.setDate(QDate.currentDate())
        self.notes_input = QTextEdit()
        self.notes_input.setFixedHeight(80)

        form.addRow("Kasa Kodu", self.code_input)
        form.addRow("Kasa Adı", self.name_input)
        form.addRow("Para Birimi", self.currency_combo)
        form.addRow("Açılış Bakiyesi", self.opening_balance)
        form.addRow("Açılış Tarihi", self.opening_date)
        form.addRow("Notlar", self.notes_input)
        layout.addLayout(form)

        row = QHBoxLayout()
        row.addStretch()
        save_btn = QPushButton("Kaydet")
        cancel_btn = QPushButton("Vazgeç")
        save_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        row.addWidget(save_btn)
        row.addWidget(cancel_btn)
        layout.addLayout(row)

        if data:
            self.code_input.setText(str(data.get("cash_code") or ""))
            self.name_input.setText(str(data.get("cash_name") or ""))
            self.currency_combo.setCurrentText(str(data.get("currency") or "USD"))
            self.opening_balance.setValue(float(data.get("opening_balance") or 0))
            date_txt = str(data.get("opening_date") or "")
            if date_txt:
                date = QDate.fromString(date_txt, "yyyy-MM-dd")
                if date.isValid():
                    self.opening_date.setDate(date)
            self.notes_input.setPlainText(str(data.get("notes") or ""))

    def payload(self) -> dict:
        if not self.code_input.text().strip() or not self.name_input.text().strip():
            raise ValueError("Code and name are required")
        return {
            "cash_code": self.code_input.text().strip(),
            "cash_name": self.name_input.text().strip(),
            "currency": self.currency_combo.currentText().strip(),
            "opening_balance": float(self.opening_balance.value()),
            "opening_date": self.opening_date.date().toString("yyyy-MM-dd"),
            "notes": self.notes_input.toPlainText().strip(),
        }


class ExchangeRateDialog(QDialog):
    def __init__(self, *, account_currency: str, voucher_currency: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Exchange Rate")
        self.resize(430, 180)

        self.account_currency = str(account_currency or "USD").strip().upper() or "USD"
        self.voucher_currency = str(voucher_currency or "USD").strip().upper() or "USD"

        layout = QVBoxLayout(self)
        message = QLabel(
            f"Customer account currency is {self.account_currency}.\n"
            f"Voucher currency is {self.voucher_currency}.\n"
            f"Please enter exchange rate."
        )
        message.setWordWrap(True)
        layout.addWidget(message)

        form = QFormLayout()
        self.rate_input = QDoubleSpinBox()
        self.rate_input.setDecimals(6)
        self.rate_input.setMaximum(999999999)
        self.rate_input.setMinimum(0.000001)
        self.rate_input.setValue(1.0)
        form.addRow(f"1 {self.voucher_currency} =", self.rate_input)
        form.addRow("", QLabel(self.account_currency))
        layout.addLayout(form)

        row = QHBoxLayout()
        row.addStretch()
        ok_btn = QPushButton("OK")
        cancel_btn = QPushButton("Cancel")
        ok_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        row.addWidget(ok_btn)
        row.addWidget(cancel_btn)
        layout.addLayout(row)

    @classmethod
    def ask_rate(cls, *, parent=None, account_currency: str, voucher_currency: str) -> float | None:
        dialog = cls(account_currency=account_currency, voucher_currency=voucher_currency, parent=parent)
        if dialog.exec():
            return float(dialog.rate_input.value())
        return None


class QuickBankDefinitionDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Yeni Banka")
        self.resize(520, 360)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.bank_name_input = QLineEdit()
        self.branch_input = QLineEdit()
        self.iban_input = QLineEdit()
        self.account_number_input = QLineEdit()
        self.currency_combo = QComboBox()
        self.currency_combo.addItems(["TRY", "USD", "EUR"])
        self.opening_balance_input = QDoubleSpinBox()
        self.opening_balance_input.setDecimals(2)
        self.opening_balance_input.setMaximum(999999999)
        self.status_combo = QComboBox()
        self.status_combo.addItems(["Aktif", "Pasif"])

        form.addRow("Banka Adı", self.bank_name_input)
        form.addRow("Şube", self.branch_input)
        form.addRow("IBAN", self.iban_input)
        form.addRow("Hesap Numarası", self.account_number_input)
        form.addRow("Para Birimi", self.currency_combo)
        form.addRow("Açılış Bakiyesi", self.opening_balance_input)
        form.addRow("Durum", self.status_combo)
        layout.addLayout(form)

        row = QHBoxLayout()
        row.addStretch()
        save_btn = QPushButton("Kaydet")
        cancel_btn = QPushButton("Vazgeç")
        save_btn.clicked.connect(self._on_accept)
        cancel_btn.clicked.connect(self.reject)
        row.addWidget(save_btn)
        row.addWidget(cancel_btn)
        layout.addLayout(row)

    def _on_accept(self):
        if not self.bank_name_input.text().strip():
            QMessageBox.warning(self, "Uyarı", "Banka adı zorunludur.")
            return
        self.accept()

    def payload(self) -> dict:
        return {
            "bank_name": self.bank_name_input.text().strip(),
            "branch_name": self.branch_input.text().strip(),
            "iban": self.iban_input.text().strip(),
            "account_number": self.account_number_input.text().strip(),
            "currency": self.currency_combo.currentText().strip(),
            "opening_balance": float(self.opening_balance_input.value()),
            "status": self.status_combo.currentText().strip(),
        }


class QuickCashDefinitionDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Yeni Kasa")
        self.resize(520, 360)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.cash_name_input = QLineEdit()
        self.currency_combo = QComboBox()
        self.currency_combo.addItems(["TRY", "USD", "EUR"])
        self.opening_balance_input = QDoubleSpinBox()
        self.opening_balance_input.setDecimals(2)
        self.opening_balance_input.setMaximum(999999999)
        self.responsible_input = QLineEdit()
        self.description_input = QTextEdit()
        self.description_input.setFixedHeight(80)
        self.status_combo = QComboBox()
        self.status_combo.addItems(["Aktif", "Pasif"])

        form.addRow("Kasa Adı", self.cash_name_input)
        form.addRow("Para Birimi", self.currency_combo)
        form.addRow("Açılış Bakiyesi", self.opening_balance_input)
        form.addRow("Sorumlu Kişi", self.responsible_input)
        form.addRow("Açıklama", self.description_input)
        form.addRow("Durum", self.status_combo)
        layout.addLayout(form)

        row = QHBoxLayout()
        row.addStretch()
        save_btn = QPushButton("Kaydet")
        cancel_btn = QPushButton("Vazgeç")
        save_btn.clicked.connect(self._on_accept)
        cancel_btn.clicked.connect(self.reject)
        row.addWidget(save_btn)
        row.addWidget(cancel_btn)
        layout.addLayout(row)

    def _on_accept(self):
        if not self.cash_name_input.text().strip():
            QMessageBox.warning(self, "Uyarı", "Kasa adı zorunludur.")
            return
        self.accept()

    def payload(self) -> dict:
        return {
            "cash_name": self.cash_name_input.text().strip(),
            "currency": self.currency_combo.currentText().strip(),
            "opening_balance": float(self.opening_balance_input.value()),
            "responsible_person": self.responsible_input.text().strip(),
            "description": self.description_input.toPlainText().strip(),
            "status": self.status_combo.currentText().strip(),
        }


class BankAccountDialog(QDialog):
    def __init__(self, parent=None, data: dict | None = None):
        super().__init__(parent)
        self.setWindowTitle("Banka Hesabı")
        self.resize(560, 420)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.code_input = QLineEdit()
        self.bank_name_input = QLineEdit()
        self.branch_input = QLineEdit()
        self.iban_input = QLineEdit()
        self.swift_input = QLineEdit()
        self.account_number_input = QLineEdit()
        self.currency_combo = QComboBox()
        self.currency_combo.addItems(["TRY", "USD", "EUR"])
        self.opening_balance = QDoubleSpinBox()
        self.opening_balance.setDecimals(2)
        self.opening_balance.setMaximum(999999999)
        self.opening_date = QDateEdit()
        self.opening_date.setCalendarPopup(True)
        self.opening_date.setDate(QDate.currentDate())
        self.notes_input = QTextEdit()
        self.notes_input.setFixedHeight(90)

        form.addRow("Banka Kodu", self.code_input)
        form.addRow("Banka Adı", self.bank_name_input)
        form.addRow("Şube", self.branch_input)
        form.addRow("IBAN", self.iban_input)
        form.addRow("SWIFT", self.swift_input)
        form.addRow("Hesap Numarası", self.account_number_input)
        form.addRow("Para Birimi", self.currency_combo)
        form.addRow("Açılış Bakiyesi", self.opening_balance)
        form.addRow("Açılış Tarihi", self.opening_date)
        form.addRow("Notlar", self.notes_input)
        layout.addLayout(form)

        row = QHBoxLayout()
        row.addStretch()
        save_btn = QPushButton("Kaydet")
        cancel_btn = QPushButton("Vazgeç")
        save_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        row.addWidget(save_btn)
        row.addWidget(cancel_btn)
        layout.addLayout(row)

        if data:
            self.code_input.setText(str(data.get("bank_code") or ""))
            self.bank_name_input.setText(str(data.get("bank_name") or ""))
            self.branch_input.setText(str(data.get("branch_name") or ""))
            self.iban_input.setText(str(data.get("iban") or ""))
            self.swift_input.setText(str(data.get("swift_code") or ""))
            self.account_number_input.setText(str(data.get("account_number") or ""))
            self.currency_combo.setCurrentText(str(data.get("currency") or "USD"))
            self.opening_balance.setValue(float(data.get("opening_balance") or 0))
            date_txt = str(data.get("opening_date") or "")
            if date_txt:
                date = QDate.fromString(date_txt, "yyyy-MM-dd")
                if date.isValid():
                    self.opening_date.setDate(date)
            self.notes_input.setPlainText(str(data.get("notes") or ""))

    def payload(self) -> dict:
        if not self.code_input.text().strip() or not self.bank_name_input.text().strip():
            raise ValueError("Bank code and bank name are required")
        return {
            "bank_code": self.code_input.text().strip(),
            "bank_name": self.bank_name_input.text().strip(),
            "branch_name": self.branch_input.text().strip(),
            "iban": self.iban_input.text().strip(),
            "swift_code": self.swift_input.text().strip(),
            "account_number": self.account_number_input.text().strip(),
            "currency": self.currency_combo.currentText().strip(),
            "opening_balance": float(self.opening_balance.value()),
            "opening_date": self.opening_date.date().toString("yyyy-MM-dd"),
            "notes": self.notes_input.toPlainText().strip(),
        }


class CollectionDialog(QDialog):
    def __init__(
        self,
        *,
        parent=None,
        customers: list[dict] | None = None,
        banks: list[dict] | None = None,
        cash_accounts: list[dict] | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Müşteri Tahsilatı")
        self.resize(580, 440)

        self.customers = customers or []
        self.banks = banks or []
        self.cash_accounts = cash_accounts or []

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.customer_combo = QComboBox()
        for row in self.customers:
            text = f"{row.get('code', '')} - {row.get('name', '')}".strip(" -")
            self.customer_combo.addItem(text, int(row.get("id") or 0))

        self.invoice_input = QLineEdit()
        self.amount_input = QDoubleSpinBox()
        self.amount_input.setDecimals(2)
        self.amount_input.setMaximum(999999999)
        self.currency_combo = QComboBox()
        self.currency_combo.addItems(["TRY", "USD", "EUR"])

        self.date_input = QDateEdit()
        self.date_input.setCalendarPopup(True)
        self.date_input.setDate(QDate.currentDate())

        self.method_combo = QComboBox()
        self.method_combo.addItems(["BANK", "CASH"])
        self.reference_input = QLineEdit()

        self.bank_combo = QComboBox()
        self.bank_combo.addItem("", 0)
        for row in self.banks:
            self.bank_combo.addItem(f"{row.get('bank_name', '')} ({row.get('currency', '')})", int(row.get("id") or 0))

        self.cash_combo = QComboBox()
        self.cash_combo.addItem("", 0)
        for row in self.cash_accounts:
            self.cash_combo.addItem(f"{row.get('cash_name', '')} ({row.get('currency', '')})", int(row.get("id") or 0))

        self.notes_input = QTextEdit()
        self.notes_input.setFixedHeight(80)

        form.addRow("Müşteri", self.customer_combo)
        form.addRow("Fatura", self.invoice_input)
        form.addRow("Tutar", self.amount_input)
        form.addRow("Para Birimi", self.currency_combo)
        form.addRow("Tahsilat Tarihi", self.date_input)
        form.addRow("Ödeme Yöntemi", self.method_combo)
        form.addRow("Referans", self.reference_input)
        form.addRow("Banka", self.bank_combo)
        form.addRow("Kasa", self.cash_combo)
        form.addRow("Notlar", self.notes_input)
        layout.addLayout(form)

        row = QHBoxLayout()
        row.addStretch()
        save_btn = QPushButton("Kaydet")
        cancel_btn = QPushButton("Vazgeç")
        save_btn.clicked.connect(self._on_accept)
        cancel_btn.clicked.connect(self.reject)
        row.addWidget(save_btn)
        row.addWidget(cancel_btn)
        layout.addLayout(row)

    def _on_accept(self):
        if self.amount_input.value() <= 0:
            QMessageBox.warning(self, "Uyarı", "Tutar 0'dan büyük olmalıdır.")
            return
        if int(self.customer_combo.currentData() or 0) <= 0:
            QMessageBox.warning(self, "Uyarı", "Müşteri seçimi zorunludur.")
            return
        self.accept()

    def payload(self) -> dict:
        method = self.method_combo.currentText().strip()
        bank_id = int(self.bank_combo.currentData() or 0)
        cash_id = int(self.cash_combo.currentData() or 0)
        if method == "BANK" and bank_id <= 0:
            raise ValueError("BANK ödeme yöntemi için banka hesabı seçin.")
        if method == "CASH" and cash_id <= 0:
            raise ValueError("CASH ödeme yöntemi için kasa hesabı seçin.")

        return {
            "customer_id": int(self.customer_combo.currentData() or 0),
            "invoice_number": self.invoice_input.text().strip(),
            "amount": float(self.amount_input.value()),
            "currency": self.currency_combo.currentText().strip(),
            "collection_date": self.date_input.date().toString("yyyy-MM-dd"),
            "payment_method": method,
            "reference_no": self.reference_input.text().strip(),
            "bank_account_id": bank_id if bank_id > 0 else None,
            "cash_account_id": cash_id if cash_id > 0 else None,
            "notes": self.notes_input.toPlainText().strip(),
        }


class SupplierPaymentDialog(QDialog):
    def __init__(
        self,
        *,
        parent=None,
        suppliers: list[dict] | None = None,
        banks: list[dict] | None = None,
        cash_accounts: list[dict] | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Tedarikçi Ödemesi")
        self.resize(580, 440)

        self.suppliers = suppliers or []
        self.banks = banks or []
        self.cash_accounts = cash_accounts or []

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.supplier_combo = QComboBox()
        for row in self.suppliers:
            text = f"{row.get('code', '')} - {row.get('name', '')}".strip(" -")
            self.supplier_combo.addItem(text, int(row.get("id") or 0))

        self.invoice_input = QLineEdit()
        self.amount_input = QDoubleSpinBox()
        self.amount_input.setDecimals(2)
        self.amount_input.setMaximum(999999999)
        self.currency_combo = QComboBox()
        self.currency_combo.addItems(["TRY", "USD", "EUR"])

        self.date_input = QDateEdit()
        self.date_input.setCalendarPopup(True)
        self.date_input.setDate(QDate.currentDate())

        self.method_combo = QComboBox()
        self.method_combo.addItems(["BANK", "CASH"])
        self.reference_input = QLineEdit()

        self.bank_combo = QComboBox()
        self.bank_combo.addItem("", 0)
        for row in self.banks:
            self.bank_combo.addItem(f"{row.get('bank_name', '')} ({row.get('currency', '')})", int(row.get("id") or 0))

        self.cash_combo = QComboBox()
        self.cash_combo.addItem("", 0)
        for row in self.cash_accounts:
            self.cash_combo.addItem(f"{row.get('cash_name', '')} ({row.get('currency', '')})", int(row.get("id") or 0))

        self.notes_input = QTextEdit()
        self.notes_input.setFixedHeight(80)

        form.addRow("Tedarikçi", self.supplier_combo)
        form.addRow("Alış Faturası", self.invoice_input)
        form.addRow("Tutar", self.amount_input)
        form.addRow("Para Birimi", self.currency_combo)
        form.addRow("Ödeme Tarihi", self.date_input)
        form.addRow("Ödeme Yöntemi", self.method_combo)
        form.addRow("Referans", self.reference_input)
        form.addRow("Banka", self.bank_combo)
        form.addRow("Kasa", self.cash_combo)
        form.addRow("Notlar", self.notes_input)
        layout.addLayout(form)

        row = QHBoxLayout()
        row.addStretch()
        save_btn = QPushButton("Kaydet")
        cancel_btn = QPushButton("Vazgeç")
        save_btn.clicked.connect(self._on_accept)
        cancel_btn.clicked.connect(self.reject)
        row.addWidget(save_btn)
        row.addWidget(cancel_btn)
        layout.addLayout(row)

    def _on_accept(self):
        if self.amount_input.value() <= 0:
            QMessageBox.warning(self, "Uyarı", "Tutar 0'dan büyük olmalıdır.")
            return
        if int(self.supplier_combo.currentData() or 0) <= 0:
            QMessageBox.warning(self, "Uyarı", "Tedarikçi seçimi zorunludur.")
            return
        self.accept()

    def payload(self) -> dict:
        method = self.method_combo.currentText().strip()
        bank_id = int(self.bank_combo.currentData() or 0)
        cash_id = int(self.cash_combo.currentData() or 0)
        if method == "BANK" and bank_id <= 0:
            raise ValueError("BANK ödeme yöntemi için banka hesabı seçin.")
        if method == "CASH" and cash_id <= 0:
            raise ValueError("CASH ödeme yöntemi için kasa hesabı seçin.")

        return {
            "supplier_id": int(self.supplier_combo.currentData() or 0),
            "purchase_invoice_number": self.invoice_input.text().strip(),
            "amount": float(self.amount_input.value()),
            "currency": self.currency_combo.currentText().strip(),
            "payment_date": self.date_input.date().toString("yyyy-MM-dd"),
            "payment_method": method,
            "reference_no": self.reference_input.text().strip(),
            "bank_account_id": bank_id if bank_id > 0 else None,
            "cash_account_id": cash_id if cash_id > 0 else None,
            "notes": self.notes_input.toPlainText().strip(),
        }


class CashMovementDialog(QDialog):
    def __init__(self, *, parent=None, movement_type: str, cash_accounts: list[dict] | None = None, banks: list[dict] | None = None):
        super().__init__(parent)
        self.movement_type = str(movement_type or "CASH_IN").strip().upper()
        self.cash_accounts = cash_accounts or []
        self.banks = banks or []

        title_map = {
            "CASH_IN": "Kasa Girişi",
            "CASH_OUT": "Kasa Çıkışı",
            "TRANSFER": "Transfer",
        }
        self.setWindowTitle(title_map.get(self.movement_type, self.movement_type.replace("_", " ").title()))
        self.resize(560, 360)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.source_cash_combo = QComboBox()
        self.source_cash_combo.addItem("", 0)
        for row in self.cash_accounts:
            self.source_cash_combo.addItem(f"{row.get('cash_code', '')} - {row.get('cash_name', '')}", int(row.get("id") or 0))

        self.target_cash_combo = QComboBox()
        self.target_cash_combo.addItem("", 0)
        for row in self.cash_accounts:
            self.target_cash_combo.addItem(f"{row.get('cash_code', '')} - {row.get('cash_name', '')}", int(row.get("id") or 0))

        self.target_bank_combo = QComboBox()
        self.target_bank_combo.addItem("", 0)
        for row in self.banks:
            self.target_bank_combo.addItem(f"{row.get('bank_code', '')} - {row.get('bank_name', '')}", int(row.get("id") or 0))

        self.amount_input = QDoubleSpinBox()
        self.amount_input.setDecimals(2)
        self.amount_input.setMaximum(999999999)
        self.currency_combo = QComboBox()
        self.currency_combo.addItems(["TRY", "USD", "EUR"])
        self.date_input = QDateEdit()
        self.date_input.setCalendarPopup(True)
        self.date_input.setDate(QDate.currentDate())
        self.reference_input = QLineEdit()
        self.description_input = QLineEdit()

        form.addRow("Kasa Hesabı", self.source_cash_combo)
        if self.movement_type == "TRANSFER":
            form.addRow("Hedef Kasa", self.target_cash_combo)
            form.addRow("Hedef Banka", self.target_bank_combo)
        form.addRow("Tutar", self.amount_input)
        form.addRow("Para Birimi", self.currency_combo)
        form.addRow("Tarih", self.date_input)
        form.addRow("Referans", self.reference_input)
        form.addRow("Açıklama", self.description_input)
        layout.addLayout(form)

        row = QHBoxLayout()
        row.addStretch()
        save_btn = QPushButton("Kaydet")
        cancel_btn = QPushButton("Vazgeç")
        save_btn.clicked.connect(self._on_accept)
        cancel_btn.clicked.connect(self.reject)
        row.addWidget(save_btn)
        row.addWidget(cancel_btn)
        layout.addLayout(row)

    def _on_accept(self):
        if self.amount_input.value() <= 0:
            QMessageBox.warning(self, "Uyarı", "Tutar 0'dan büyük olmalıdır.")
            return
        if int(self.source_cash_combo.currentData() or 0) <= 0:
            QMessageBox.warning(self, "Uyarı", "Kasa hesabı seçimi zorunludur.")
            return
        if self.movement_type == "TRANSFER":
            if int(self.target_cash_combo.currentData() or 0) <= 0 and int(self.target_bank_combo.currentData() or 0) <= 0:
                QMessageBox.warning(self, "Uyarı", "Hedef kasa veya hedef banka hesabı seçin.")
                return
        self.accept()

    def payload(self) -> dict:
        return {
            "movement_type": self.movement_type,
            "transaction_date": self.date_input.date().toString("yyyy-MM-dd"),
            "amount": float(self.amount_input.value()),
            "currency": self.currency_combo.currentText().strip(),
            "source_cash_account_id": int(self.source_cash_combo.currentData() or 0) or None,
            "target_cash_account_id": int(self.target_cash_combo.currentData() or 0) or None,
            "target_bank_account_id": int(self.target_bank_combo.currentData() or 0) or None,
            "reference_no": self.reference_input.text().strip(),
            "description": self.description_input.text().strip(),
        }
