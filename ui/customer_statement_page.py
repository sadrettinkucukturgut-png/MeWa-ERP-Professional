from __future__ import annotations

from PySide6.QtWidgets import QComboBox

from models.finance_model import FinanceModel
from ui.finance_base_page import FinanceBasePage


class CustomerStatementPage(FinanceBasePage):
    def __init__(self):
        super().__init__(
            title="📄 Customer Statement",
            layout_key="finance_customer_statement_table",
            column_labels=["Date", "Type", "Reference", "Description", "Currency", "Debit", "Credit", "Balance"],
            stat_titles=["Opening Balance", "Closing Balance", "Total Debit", "Total Credit"],
        )

        self.customer_combo = QComboBox()
        self.toolbar.insertWidget(self.action_new, self.customer_combo)
        self.customer_combo.currentIndexChanged.connect(self.load_data)

        self.action_new.setEnabled(False)
        self.action_edit.setEnabled(False)
        self.action_delete.setEnabled(False)

        self._load_customers()
        self.load_data()

    def _load_customers(self):
        self.customer_combo.clear()
        self.customer_combo.addItem("", 0)
        for row in FinanceModel.list_customers():
            self.customer_combo.addItem(f"{row.get('code', '')} - {row.get('name', '')}".strip(" -"), int(row.get("id") or 0))

    def load_data(self, keyword: str = ""):
        customer_id = int(self.customer_combo.currentData() or 0)
        if customer_id <= 0:
            self.set_table_rows([])
            self.set_stats({
                "Opening Balance": "0.00",
                "Closing Balance": "0.00",
                "Total Debit": "0.00",
                "Total Credit": "0.00",
            })
            return

        rows = FinanceModel.customer_statement(customer_id)
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
                opening = balance - (debit - credit)
            closing = balance
            table_rows.append(
                [
                    str(row.get("date") or ""),
                    str(row.get("type") or ""),
                    str(row.get("reference") or ""),
                    str(row.get("description") or ""),
                    str(row.get("currency") or "USD"),
                    f"{debit:,.2f}",
                    f"{credit:,.2f}",
                    f"{balance:,.2f}",
                ]
            )

        self.set_table_rows(table_rows)
        self.set_stats(
            {
                "Opening Balance": f"{opening:,.2f}",
                "Closing Balance": f"{closing:,.2f}",
                "Total Debit": f"{total_debit:,.2f}",
                "Total Credit": f"{total_credit:,.2f}",
            }
        )
