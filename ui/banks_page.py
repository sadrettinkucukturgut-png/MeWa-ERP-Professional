from __future__ import annotations

from PySide6.QtWidgets import QMessageBox

from models.finance_model import FinanceModel
from ui.finance_base_page import FinanceBasePage
from ui.finance_dialogs import BankAccountDialog


class BanksPage(FinanceBasePage):
    def __init__(self):
        super().__init__(
            title="🏦 Banks",
            layout_key="finance_banks_table",
            column_labels=[
                "ID",
                "Bank Code",
                "Bank Name",
                "Branch",
                "IBAN",
                "SWIFT",
                "Account Number",
                "Currency",
                "Opening Balance",
                "Current Balance",
                "Opening Date",
                "Notes",
            ],
            stat_titles=["Total Banks", "TRY", "USD", "EUR"],
        )
        self.load_data()

    def load_data(self, keyword: str = ""):
        rows = FinanceModel.list_bank_accounts(keyword)
        table_rows = []
        totals = {"TRY": 0.0, "USD": 0.0, "EUR": 0.0}
        total_bank = 0.0
        for row in rows:
            bal = float(row.get("current_balance") or 0)
            cur = str(row.get("currency") or "USD")
            total_bank += bal
            totals[cur] = totals.get(cur, 0.0) + bal
            table_rows.append(
                [
                    str(row.get("id") or ""),
                    str(row.get("bank_code") or ""),
                    str(row.get("bank_name") or ""),
                    str(row.get("branch_name") or ""),
                    str(row.get("iban") or ""),
                    str(row.get("swift_code") or ""),
                    str(row.get("account_number") or ""),
                    cur,
                    f"{float(row.get('opening_balance') or 0):,.2f}",
                    f"{bal:,.2f}",
                    str(row.get("opening_date") or ""),
                    str(row.get("notes") or ""),
                ]
            )
        self.set_table_rows(table_rows)
        self.set_stats(
            {
                "Total Banks": f"{total_bank:,.2f}",
                "TRY": f"{totals.get('TRY', 0.0):,.2f}",
                "USD": f"{totals.get('USD', 0.0):,.2f}",
                "EUR": f"{totals.get('EUR', 0.0):,.2f}",
            }
        )

    def _selected_id(self) -> int:
        row = self.table.currentRow()
        if row < 0:
            return 0
        item = self.table.item(row, 0)
        if item is None:
            return 0
        try:
            return int(item.text().strip() or 0)
        except Exception:
            return 0

    def _find_raw_row(self, bank_id: int) -> dict | None:
        for row in FinanceModel.list_bank_accounts(self.search_input.text()):
            if int(row.get("id") or 0) == bank_id:
                return row
        return None

    def _on_new(self):
        dlg = BankAccountDialog(self)
        if not dlg.exec():
            return
        try:
            FinanceModel.save_bank_account(bank_id=None, **dlg.payload())
            self.load_data(self.search_input.text())
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))

    def _on_edit(self):
        bank_id = self._selected_id()
        if bank_id <= 0:
            return
        data = self._find_raw_row(bank_id)
        if not data:
            return
        dlg = BankAccountDialog(self, data=data)
        if not dlg.exec():
            return
        try:
            FinanceModel.save_bank_account(bank_id=bank_id, **dlg.payload())
            self.load_data(self.search_input.text())
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))

    def _on_delete(self):
        bank_id = self._selected_id()
        if bank_id <= 0:
            return
        answer = QMessageBox.question(self, "Delete", "Delete selected bank account?")
        if answer != QMessageBox.Yes:
            return
        try:
            FinanceModel.delete_bank_account(bank_id)
            self.load_data(self.search_input.text())
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))
