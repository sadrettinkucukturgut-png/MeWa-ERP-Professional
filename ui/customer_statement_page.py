from __future__ import annotations

from datetime import date

from PySide6.QtCore import QDate
from PySide6.QtWidgets import QComboBox, QDateEdit, QHBoxLayout, QLabel, QLineEdit, QPushButton, QWidget

from models.finance_model import FinanceModel
from ui.finance_base_page import FinanceBasePage


class CustomerStatementPage(FinanceBasePage):
    def __init__(self):
        super().__init__(
            title="📄 Müşteri Ekstresi",
            layout_key="finance_customer_statement_table",
            column_labels=["Tarih", "Tür", "Referans", "Açıklama", "Para Birimi", "Borç", "Alacak", "Bakiye"],
            stat_titles=["Açılış Bakiyesi", "Toplam Borç", "Toplam Alacak", "Kapanış Bakiyesi"],
        )

        self.search_input.setVisible(False)

        control_row = QWidget()
        control_layout = QHBoxLayout(control_row)
        control_layout.setContentsMargins(0, 0, 0, 0)
        control_layout.setSpacing(8)

        self.customer_combo = QComboBox()
        self.customer_combo.setMinimumWidth(220)
        self.customer_combo.currentIndexChanged.connect(self._on_customer_changed)
        self.customer_code_input = QLineEdit()
        self.customer_code_input.setReadOnly(True)
        self.customer_code_input.setPlaceholderText("Müşteri Kodu")
        self.company_name_input = QLineEdit()
        self.company_name_input.setReadOnly(True)
        self.company_name_input.setPlaceholderText("Firma Ünvanı")
        self.current_balance_input = QLineEdit()
        self.current_balance_input.setReadOnly(True)
        self.current_balance_input.setPlaceholderText("Güncel Bakiye")

        self.start_date = QDateEdit()
        self.start_date.setCalendarPopup(True)
        first_day = date.today().replace(month=1, day=1)
        self.start_date.setDate(QDate(first_day.year, first_day.month, first_day.day))
        self.end_date = QDateEdit()
        self.end_date.setCalendarPopup(True)
        self.end_date.setDate(QDate.currentDate())
        self.load_button = QPushButton("Yükle")
        self.load_button.clicked.connect(lambda: self.load_data(self.toolbar_search_input.text().strip()))

        control_layout.addWidget(QLabel("Müşteri"))
        control_layout.addWidget(self.customer_combo)
        control_layout.addWidget(QLabel("Müşteri Kodu"))
        control_layout.addWidget(self.customer_code_input)
        control_layout.addWidget(QLabel("Firma Ünvanı"))
        control_layout.addWidget(self.company_name_input)
        control_layout.addWidget(QLabel("Güncel Bakiye"))
        control_layout.addWidget(self.current_balance_input)
        control_layout.addWidget(QLabel("Başlangıç"))
        control_layout.addWidget(self.start_date)
        control_layout.addWidget(QLabel("Bitiş"))
        control_layout.addWidget(self.end_date)
        control_layout.addWidget(self.load_button)

        self.toolbar.insertWidget(self.action_new, control_row)
        self.toolbar.addSeparator()

        self.toolbar_search_input = QLineEdit()
        self.toolbar_search_input.setPlaceholderText("Tabloda ara")
        self.toolbar.insertWidget(self.action_search, self.toolbar_search_input)
        self.action_search.triggered.connect(lambda: self.load_data(self.toolbar_search_input.text().strip()))

        self.action_new.setEnabled(False)
        self.action_edit.setEnabled(False)
        self.action_delete.setEnabled(False)

        self._listener = self._on_finance_changed
        FinanceModel.register_listener(self._listener)

        self._load_customers()
        self.load_data()

    def _on_finance_changed(self, _event: str):
        current_id = int(self.customer_combo.currentData() or 0)
        self._load_customers()
        if current_id > 0:
            for i in range(self.customer_combo.count()):
                if int(self.customer_combo.itemData(i) or 0) == current_id:
                    self.customer_combo.setCurrentIndex(i)
                    break
        self.load_data(self.toolbar_search_input.text().strip())

    def _load_customers(self):
        self.customer_combo.clear()
        self.customer_combo.addItem("Müşteri seçiniz", 0)
        for row in FinanceModel.list_customers():
            self.customer_combo.addItem(f"{row.get('code', '')} - {row.get('name', '')}".strip(" -"), int(row.get("id") or 0))

    def _set_balance_badge(self, balance: float, currency: str):
        curr = str(currency or "USD").strip().upper() or "USD"
        if balance > 0:
            self.current_balance_input.setText(f"{balance:,.2f} {curr} (ALACAKLIYIZ)")
            self.current_balance_input.setStyleSheet("color:#16a34a; font-weight:700;")
        elif balance < 0:
            self.current_balance_input.setText(f"{abs(balance):,.2f} {curr} (BORÇLUYUZ)")
            self.current_balance_input.setStyleSheet("color:#dc2626; font-weight:700;")
        else:
            self.current_balance_input.setText(f"BAKIYE YOK (0.00 {curr})")
            self.current_balance_input.setStyleSheet("color:#94a3b8; font-weight:700;")

    def _on_customer_changed(self):
        customer_id = int(self.customer_combo.currentData() or 0)
        if customer_id <= 0:
            self.customer_code_input.clear()
            self.company_name_input.clear()
            self._set_balance_badge(0.0, "USD")
            self.set_table_rows([])
            return
        summary = FinanceModel.customer_summary(customer_id)
        self.customer_code_input.setText(str(summary.get("code") or ""))
        self.company_name_input.setText(str(summary.get("name") or ""))
        self._set_balance_badge(float(summary.get("balance") or 0), str(summary.get("currency") or "USD"))

    def load_data(self, keyword: str = ""):
        customer_id = int(self.customer_combo.currentData() or 0)
        if customer_id <= 0:
            self.set_table_rows([])
            self.set_stats({
                "Açılış Bakiyesi": "0.00",
                "Kapanış Bakiyesi": "0.00",
                "Toplam Borç": "0.00",
                "Toplam Alacak": "0.00",
            })
            return

        summary = FinanceModel.customer_summary(customer_id)
        account_currency = str(summary.get("currency") or "USD")
        self._set_balance_badge(float(summary.get("balance") or 0), account_currency)

        start_date = self.start_date.date().toString("yyyy-MM-dd")
        end_date = self.end_date.date().toString("yyyy-MM-dd")
        rows = FinanceModel.customer_statement(customer_id, start_date=start_date, end_date=end_date)
        if keyword.strip():
            token = keyword.strip().lower()
            rows = [
                row for row in rows if token in str(row.get("reference", "")).lower() or token in str(row.get("description", "")).lower()
            ]

        table_rows = []
        total_debit = 0.0
        total_credit = 0.0
        opening = 0.0
        closing = 0.0
        for idx, row in enumerate(rows):
            debit = float(row.get("debit") or 0)
            credit = float(row.get("credit") or 0)
            balance = float(row.get("balance") or 0)
            total_debit += debit
            total_credit += credit
            if idx == 0:
                opening = balance - (credit - debit)
            closing = balance
            balance_text = f"{balance:,.2f}"
            if balance > 0:
                balance_text = f"{balance:,.2f} {account_currency} (ALACAKLIYIZ)"
            elif balance < 0:
                balance_text = f"{abs(balance):,.2f} {account_currency} (BORÇLUYUZ)"
            table_rows.append(
                [
                    str(row.get("date") or ""),
                    str(row.get("type") or ""),
                    str(row.get("reference") or ""),
                    str(row.get("description") or ""),
                    str(row.get("currency") or "USD"),
                    f"{debit:,.2f}",
                    f"{credit:,.2f}",
                    balance_text,
                ]
            )

        self.set_table_rows(table_rows)
        self.set_stats(
            {
                "Açılış Bakiyesi": f"{opening:,.2f}",
                "Kapanış Bakiyesi": f"{closing:,.2f}",
                "Toplam Borç": f"{total_debit:,.2f}",
                "Toplam Alacak": f"{total_credit:,.2f}",
            }
        )

    def closeEvent(self, event):  # noqa: N802
        FinanceModel.unregister_listener(self._listener)
        super().closeEvent(event)
