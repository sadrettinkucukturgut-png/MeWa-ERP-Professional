from __future__ import annotations

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)


class CashAccountDialog(QDialog):
    def __init__(self, parent=None, data: dict | None = None):
        super().__init__(parent)
        self.setWindowTitle("Cash Account")
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

        form.addRow("Cash Code", self.code_input)
        form.addRow("Cash Name", self.name_input)
        form.addRow("Currency", self.currency_combo)
        form.addRow("Opening Balance", self.opening_balance)
        form.addRow("Opening Date", self.opening_date)
        form.addRow("Notes", self.notes_input)
        layout.addLayout(form)

        row = QHBoxLayout()
        row.addStretch()
        save_btn = QPushButton("Save")
        cancel_btn = QPushButton("Cancel")
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


class BankAccountDialog(QDialog):
    def __init__(self, parent=None, data: dict | None = None):
        super().__init__(parent)
        self.setWindowTitle("Bank Account")
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

        form.addRow("Bank Code", self.code_input)
        form.addRow("Bank Name", self.bank_name_input)
        form.addRow("Branch", self.branch_input)
        form.addRow("IBAN", self.iban_input)
        form.addRow("SWIFT", self.swift_input)
        form.addRow("Account Number", self.account_number_input)
        form.addRow("Currency", self.currency_combo)
        form.addRow("Opening Balance", self.opening_balance)
        form.addRow("Opening Date", self.opening_date)
        form.addRow("Notes", self.notes_input)
        layout.addLayout(form)

        row = QHBoxLayout()
        row.addStretch()
        save_btn = QPushButton("Save")
        cancel_btn = QPushButton("Cancel")
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
        self.setWindowTitle("Customer Collection")
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

        form.addRow("Customer", self.customer_combo)
        form.addRow("Invoice", self.invoice_input)
        form.addRow("Amount", self.amount_input)
        form.addRow("Currency", self.currency_combo)
        form.addRow("Collection Date", self.date_input)
        form.addRow("Payment Method", self.method_combo)
        form.addRow("Reference", self.reference_input)
        form.addRow("Bank", self.bank_combo)
        form.addRow("Cash", self.cash_combo)
        form.addRow("Notes", self.notes_input)
        layout.addLayout(form)

        row = QHBoxLayout()
        row.addStretch()
        save_btn = QPushButton("Save")
        cancel_btn = QPushButton("Cancel")
        save_btn.clicked.connect(self._on_accept)
        cancel_btn.clicked.connect(self.reject)
        row.addWidget(save_btn)
        row.addWidget(cancel_btn)
        layout.addLayout(row)

    def _on_accept(self):
        if self.amount_input.value() <= 0:
            QMessageBox.warning(self, "Warning", "Amount must be greater than 0.")
            return
        if int(self.customer_combo.currentData() or 0) <= 0:
            QMessageBox.warning(self, "Warning", "Customer is required.")
            return
        self.accept()

    def payload(self) -> dict:
        method = self.method_combo.currentText().strip()
        bank_id = int(self.bank_combo.currentData() or 0)
        cash_id = int(self.cash_combo.currentData() or 0)
        if method == "BANK" and bank_id <= 0:
            raise ValueError("Select bank account for BANK payment method")
        if method == "CASH" and cash_id <= 0:
            raise ValueError("Select cash account for CASH payment method")

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
        self.setWindowTitle("Supplier Payment")
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

        form.addRow("Supplier", self.supplier_combo)
        form.addRow("Purchase Invoice", self.invoice_input)
        form.addRow("Amount", self.amount_input)
        form.addRow("Currency", self.currency_combo)
        form.addRow("Payment Date", self.date_input)
        form.addRow("Payment Method", self.method_combo)
        form.addRow("Reference", self.reference_input)
        form.addRow("Bank", self.bank_combo)
        form.addRow("Cash", self.cash_combo)
        form.addRow("Notes", self.notes_input)
        layout.addLayout(form)

        row = QHBoxLayout()
        row.addStretch()
        save_btn = QPushButton("Save")
        cancel_btn = QPushButton("Cancel")
        save_btn.clicked.connect(self._on_accept)
        cancel_btn.clicked.connect(self.reject)
        row.addWidget(save_btn)
        row.addWidget(cancel_btn)
        layout.addLayout(row)

    def _on_accept(self):
        if self.amount_input.value() <= 0:
            QMessageBox.warning(self, "Warning", "Amount must be greater than 0.")
            return
        if int(self.supplier_combo.currentData() or 0) <= 0:
            QMessageBox.warning(self, "Warning", "Supplier is required.")
            return
        self.accept()

    def payload(self) -> dict:
        method = self.method_combo.currentText().strip()
        bank_id = int(self.bank_combo.currentData() or 0)
        cash_id = int(self.cash_combo.currentData() or 0)
        if method == "BANK" and bank_id <= 0:
            raise ValueError("Select bank account for BANK payment method")
        if method == "CASH" and cash_id <= 0:
            raise ValueError("Select cash account for CASH payment method")

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

        self.setWindowTitle(self.movement_type.replace("_", " ").title())
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

        form.addRow("Cash Account", self.source_cash_combo)
        if self.movement_type == "TRANSFER":
            form.addRow("Target Cash", self.target_cash_combo)
            form.addRow("Target Bank", self.target_bank_combo)
        form.addRow("Amount", self.amount_input)
        form.addRow("Currency", self.currency_combo)
        form.addRow("Date", self.date_input)
        form.addRow("Reference", self.reference_input)
        form.addRow("Description", self.description_input)
        layout.addLayout(form)

        row = QHBoxLayout()
        row.addStretch()
        save_btn = QPushButton("Post")
        cancel_btn = QPushButton("Cancel")
        save_btn.clicked.connect(self._on_accept)
        cancel_btn.clicked.connect(self.reject)
        row.addWidget(save_btn)
        row.addWidget(cancel_btn)
        layout.addLayout(row)

    def _on_accept(self):
        if self.amount_input.value() <= 0:
            QMessageBox.warning(self, "Warning", "Amount must be greater than 0.")
            return
        if int(self.source_cash_combo.currentData() or 0) <= 0:
            QMessageBox.warning(self, "Warning", "Cash account is required.")
            return
        if self.movement_type == "TRANSFER":
            if int(self.target_cash_combo.currentData() or 0) <= 0 and int(self.target_bank_combo.currentData() or 0) <= 0:
                QMessageBox.warning(self, "Warning", "Select target cash or target bank account.")
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
