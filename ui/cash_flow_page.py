from __future__ import annotations

from datetime import datetime, timedelta

from models.finance_model import FinanceModel
from ui.finance_base_page import FinanceBasePage


class CashFlowPage(FinanceBasePage):
    def __init__(self):
        super().__init__(
            title="📊 Cash Flow",
            layout_key="finance_cash_flow_table",
            column_labels=["Period", "Expected Collections", "Expected Payments", "Net", "Status"],
            stat_titles=["Total Cash", "Today's Collections", "Today's Payments", "Net Cash"],
        )
        self.action_new.setEnabled(False)
        self.action_edit.setEnabled(False)
        self.action_delete.setEnabled(False)
        self.load_data()

    def load_data(self, keyword: str = ""):
        summary = FinanceModel.cash_flow_summary()
        today = datetime.now().date()
        tomorrow = today + timedelta(days=1)
        next_week = today + timedelta(days=7)
        next_month = today + timedelta(days=30)

        receivables = float(summary.get("receivables") or 0)
        payables = float(summary.get("payables") or 0)

        rows = [
            [str(today), f"{float(summary.get('today_collections') or 0):,.2f}", f"{float(summary.get('today_payments') or 0):,.2f}", f"{float(summary.get('today_collections') or 0) - float(summary.get('today_payments') or 0):,.2f}", "Today"],
            [str(tomorrow), f"{(receivables * 0.05):,.2f}", f"{(payables * 0.05):,.2f}", f"{(receivables - payables) * 0.05:,.2f}", "Tomorrow"],
            [str(next_week), f"{(receivables * 0.25):,.2f}", f"{(payables * 0.25):,.2f}", f"{(receivables - payables) * 0.25:,.2f}", "Next Week"],
            [str(next_month), f"{(receivables * 0.60):,.2f}", f"{(payables * 0.60):,.2f}", f"{(receivables - payables) * 0.60:,.2f}", "Next Month"],
        ]

        if keyword.strip():
            token = keyword.strip().lower()
            rows = [row for row in rows if token in row[0].lower() or token in row[4].lower()]

        self.set_table_rows(rows)
        self.set_stats(
            {
                "Total Cash": f"{float(summary.get('total_cash') or 0) + float(summary.get('total_banks') or 0):,.2f}",
                "Today's Collections": f"{float(summary.get('today_collections') or 0):,.2f}",
                "Today's Payments": f"{float(summary.get('today_payments') or 0):,.2f}",
                "Net Cash": f"{float(summary.get('net_cash') or 0):,.2f}",
            }
        )
