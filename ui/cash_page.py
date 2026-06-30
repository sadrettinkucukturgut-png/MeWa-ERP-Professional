from __future__ import annotations

from PySide6.QtWidgets import QMessageBox

from models.finance_model import FinanceModel
from ui.finance_base_page import FinanceBasePage
from ui.finance_dialogs import CashAccountDialog, CashMovementDialog


class CashPage(FinanceBasePage):
    def __init__(self):
        super().__init__(
            title="💵 Cash",
            layout_key="finance_cash_table",
            column_labels=["ID", "Cash Code", "Cash Name", "Currency", "Opening Balance", "Current Balance", "Opening Date", "Notes"],
            stat_titles=["Total Cash", "TRY", "USD", "EUR"],
        )
        self.action_cash_in = self.toolbar.addAction("Cash In")
        self.action_cash_out = self.toolbar.addAction("Cash Out")
        self.action_transfer = self.toolbar.addAction("Transfer")
        self.action_cash_in.triggered.connect(lambda: self._post_movement("CASH_IN"))
        self.action_cash_out.triggered.connect(lambda: self._post_movement("CASH_OUT"))
        self.action_transfer.triggered.connect(lambda: self._post_movement("TRANSFER"))
        self.load_data()

    def load_data(self, keyword: str = ""):
        rows = FinanceModel.list_cash_accounts(keyword)
        table_rows = []
        totals = {"TRY": 0.0, "USD": 0.0, "EUR": 0.0}
        total_cash = 0.0
        for row in rows:
            bal = float(row.get("current_balance") or 0)
            cur = str(row.get("currency") or "USD")
            total_cash += bal
            totals[cur] = totals.get(cur, 0.0) + bal
            table_rows.append(
                [
                    str(row.get("id") or ""),
                    str(row.get("cash_code") or ""),
                    str(row.get("cash_name") or ""),
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
                "Total Cash": f"{total_cash:,.2f}",
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

    def _find_raw_row(self, cash_id: int) -> dict | None:
        for row in FinanceModel.list_cash_accounts(self.search_input.text()):
            if int(row.get("id") or 0) == cash_id:
                return row
        return None

    def _on_new(self):
        dlg = CashAccountDialog(self)
        if not dlg.exec():
            return
        try:
            FinanceModel.save_cash_account(cash_id=None, **dlg.payload())
            self.load_data(self.search_input.text())
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))

    def _on_edit(self):
        cash_id = self._selected_id()
        if cash_id <= 0:
            return
        data = self._find_raw_row(cash_id)
        if not data:
            return
        dlg = CashAccountDialog(self, data=data)
        if not dlg.exec():
            return
        try:
            FinanceModel.save_cash_account(cash_id=cash_id, **dlg.payload())
            self.load_data(self.search_input.text())
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))

    def _on_delete(self):
        cash_id = self._selected_id()
        if cash_id <= 0:
            return
        answer = QMessageBox.question(self, "Delete", "Delete selected cash account?")
        if answer != QMessageBox.Yes:
            return
        try:
            FinanceModel.delete_cash_account(cash_id)
            self.load_data(self.search_input.text())
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))

    def _post_movement(self, movement_type: str):
        dlg = CashMovementDialog(
            parent=self,
            movement_type=movement_type,
            cash_accounts=FinanceModel.list_cash_accounts(),
            banks=FinanceModel.list_bank_accounts(),
        )
        if not dlg.exec():
            return
        try:
            FinanceModel.post_cash_movement(**dlg.payload())
            self.load_data(self.search_input.text())
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))
