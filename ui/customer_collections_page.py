from __future__ import annotations

from PySide6.QtWidgets import QMessageBox

from models.finance_model import FinanceModel
from ui.finance_base_page import FinanceBasePage
from ui.finance_dialogs import CollectionDialog


class CustomerCollectionsPage(FinanceBasePage):
    def __init__(self):
        super().__init__(
            title="💳 Customer Collections",
            layout_key="finance_customer_collections_table",
            column_labels=[
                "ID",
                "Date",
                "Collection No",
                "Customer",
                "Invoice",
                "Amount",
                "Currency",
                "Payment Method",
                "Reference",
                "Bank/Cash",
                "Notes",
            ],
            stat_titles=["Today's Collections", "Total Collections", "Receivables", "Records"],
        )
        self.load_data()

    def load_data(self, keyword: str = ""):
        rows = FinanceModel.list_customer_collections(keyword)
        table_rows = []
        total = 0.0
        today_total = 0.0
        today = FinanceModel._now_date()
        for row in rows:
            amount = float(row.get("amount") or 0)
            total += amount
            if str(row.get("collection_date") or "") == today:
                today_total += amount
            table_rows.append(
                [
                    str(row.get("id") or ""),
                    str(row.get("collection_date") or ""),
                    str(row.get("collection_no") or ""),
                    str(row.get("customer_name") or ""),
                    str(row.get("invoice_number") or ""),
                    f"{amount:,.2f}",
                    str(row.get("currency") or "USD"),
                    str(row.get("payment_method") or ""),
                    str(row.get("reference_no") or ""),
                    str(row.get("bank_or_cash") or ""),
                    str(row.get("notes") or ""),
                ]
            )

        summary = FinanceModel.cash_flow_summary()
        self.set_table_rows(table_rows)
        self.set_stats(
            {
                "Today's Collections": f"{today_total:,.2f}",
                "Total Collections": f"{total:,.2f}",
                "Receivables": f"{float(summary.get('receivables') or 0):,.2f}",
                "Records": str(len(rows)),
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

    def _on_new(self):
        dlg = CollectionDialog(
            parent=self,
            customers=FinanceModel.list_customers(),
            banks=FinanceModel.list_bank_accounts(),
            cash_accounts=FinanceModel.list_cash_accounts(),
        )
        if not dlg.exec():
            return
        try:
            FinanceModel.create_customer_collection(**dlg.payload())
            self.load_data(self.search_input.text())
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))

    def _on_edit(self):
        QMessageBox.information(self, "Info", "Collections are immutable after posting. Use delete and recreate.")

    def _on_delete(self):
        selected_id = self._selected_id()
        if selected_id <= 0:
            return
        answer = QMessageBox.question(self, "Delete", "Delete selected collection? This will rollback balances.")
        if answer != QMessageBox.Yes:
            return
        try:
            FinanceModel.delete_customer_collection(selected_id)
            self.load_data(self.search_input.text())
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))
