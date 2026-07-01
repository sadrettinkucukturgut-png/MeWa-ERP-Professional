from __future__ import annotations

from datetime import datetime, timedelta

from models.finance_model import FinanceModel
from ui.finance_base_page import FinanceBasePage


class CashFlowPage(FinanceBasePage):
    def __init__(self):
        super().__init__(
            title="📊 Nakit Akışı",
            layout_key="finance_cash_flow_table",
            column_labels=["Dönem", "Beklenen Tahsilat", "Beklenen Ödeme", "Net", "Durum"],
            stat_titles=["Toplam Nakit", "Bugünkü Tahsilat", "Bugünkü Ödeme", "Net Nakit"],
        )
        self.action_new.setEnabled(False)
        self.action_edit.setEnabled(False)
        self.action_delete.setEnabled(False)
        self._listener = self._on_finance_changed
        FinanceModel.register_listener(self._listener)
        self.load_data()

    def _on_finance_changed(self, _event: str):
        self.load_data(self.search_input.text().strip())

    def load_data(self, keyword: str = ""):
        summary = FinanceModel.cash_flow_summary()
        today = datetime.now().date()
        tomorrow = today + timedelta(days=1)
        next_week = today + timedelta(days=7)
        next_month = today + timedelta(days=30)

        receivables = float(summary.get("receivables") or 0)
        payables = float(summary.get("payables") or 0)

        rows = [
            [str(today), f"{float(summary.get('today_collections') or 0):,.2f}", f"{float(summary.get('today_payments') or 0):,.2f}", f"{float(summary.get('today_collections') or 0) - float(summary.get('today_payments') or 0):,.2f}", "Bugün"],
            [str(tomorrow), f"{(receivables * 0.05):,.2f}", f"{(payables * 0.05):,.2f}", f"{(receivables - payables) * 0.05:,.2f}", "Yarın"],
            [str(next_week), f"{(receivables * 0.25):,.2f}", f"{(payables * 0.25):,.2f}", f"{(receivables - payables) * 0.25:,.2f}", "Gelecek Hafta"],
            [str(next_month), f"{(receivables * 0.60):,.2f}", f"{(payables * 0.60):,.2f}", f"{(receivables - payables) * 0.60:,.2f}", "Gelecek Ay"],
        ]

        if keyword.strip():
            token = keyword.strip().lower()
            rows = [row for row in rows if token in row[0].lower() or token in row[4].lower()]

        self.set_table_rows(rows)
        self.set_stats(
            {
                "Toplam Nakit": f"{float(summary.get('total_cash') or 0) + float(summary.get('total_banks') or 0):,.2f}",
                "Bugünkü Tahsilat": f"{float(summary.get('today_collections') or 0):,.2f}",
                "Bugünkü Ödeme": f"{float(summary.get('today_payments') or 0):,.2f}",
                "Net Nakit": f"{float(summary.get('net_cash') or 0):,.2f}",
            }
        )

    def closeEvent(self, event):  # noqa: N802
        FinanceModel.unregister_listener(self._listener)
        super().closeEvent(event)
