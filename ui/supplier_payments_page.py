from __future__ import annotations

from PySide6.QtWidgets import QMessageBox

from models.finance_model import FinanceModel
from ui.finance_base_page import FinanceBasePage
from ui.finance_dialogs import SupplierPaymentDialog


class SupplierPaymentsPage(FinanceBasePage):
    def __init__(self):
        super().__init__(
            title="💸 Supplier Payments",
            layout_key="finance_supplier_payments_table",
            column_labels=[
                "ID",
                "Date",
                "Payment No",
                "Supplier",
                "Purchase Invoice",
                "Amount",
                "Currency",
                "Payment Method",
                "Reference",
                "Bank/Cash",
                "Notes",
            ],
            stat_titles=["Today's Payments", "Total Payments", "Payables", "Records"],
        )
        self.load_data()

    def load_data(self, keyword: str = ""):
        rows = FinanceModel.list_supplier_payments(keyword)
        table_rows = []
        total = 0.0
        today_total = 0.0
        today = FinanceModel._now_date()
        for row in rows:
            amount = float(row.get("amount") or 0)
            total += amount
            if str(row.get("payment_date") or "") == today:
                today_total += amount
            table_rows.append(
                [
                    str(row.get("id") or ""),
                    str(row.get("payment_date") or ""),
                    str(row.get("payment_no") or ""),
                    str(row.get("supplier_name") or ""),
                    str(row.get("purchase_invoice_number") or ""),
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
                "Today's Payments": f"{today_total:,.2f}",
                "Total Payments": f"{total:,.2f}",
                "Payables": f"{float(summary.get('payables') or 0):,.2f}",
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
        dlg = SupplierPaymentDialog(
            parent=self,
            suppliers=FinanceModel.list_suppliers(),
            banks=FinanceModel.list_bank_accounts(),
            cash_accounts=FinanceModel.list_cash_accounts(),
        )
        if not dlg.exec():
            return
        try:
            FinanceModel.create_supplier_payment(**dlg.payload())
            self.load_data(self.search_input.text())
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))

    def _on_edit(self):
        QMessageBox.information(self, "Info", "Payments are immutable after posting. Use delete and recreate.")

    def _on_delete(self):
        selected_id = self._selected_id()
        if selected_id <= 0:
            return
        answer = QMessageBox.question(self, "Delete", "Delete selected payment? This will rollback balances.")
        if answer != QMessageBox.Yes:
            return
        try:
            FinanceModel.delete_supplier_payment(selected_id)
            self.load_data(self.search_input.text())
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))
