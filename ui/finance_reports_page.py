from __future__ import annotations

from models.finance_model import FinanceModel
from ui.finance_base_page import FinanceBasePage


class FinanceReportsPage(FinanceBasePage):
    def __init__(self):
        super().__init__(
            title="📈 Finance Reports",
            layout_key="finance_reports_table",
            column_labels=["Report", "Metric", "Value", "Currency", "Last Updated"],
            stat_titles=["Cash Report", "Bank Report", "Receivables", "Payables"],
        )
        self.action_new.setEnabled(False)
        self.action_edit.setEnabled(False)
        self.action_delete.setEnabled(False)
        self.load_data()

    def load_data(self, keyword: str = ""):
        summary = FinanceModel.cash_flow_summary()
        rows = [
            ["Cash Report", "Total Cash", f"{float(summary.get('total_cash') or 0):,.2f}", "Multi", FinanceModel._now_date()],
            ["Bank Report", "Total Banks", f"{float(summary.get('total_banks') or 0):,.2f}", "Multi", FinanceModel._now_date()],
            ["Collections Report", "Today's Collections", f"{float(summary.get('today_collections') or 0):,.2f}", "Multi", FinanceModel._now_date()],
            ["Payments Report", "Today's Payments", f"{float(summary.get('today_payments') or 0):,.2f}", "Multi", FinanceModel._now_date()],
            ["Receivable Aging", "Receivables", f"{float(summary.get('receivables') or 0):,.2f}", "Multi", FinanceModel._now_date()],
            ["Payable Aging", "Payables", f"{float(summary.get('payables') or 0):,.2f}", "Multi", FinanceModel._now_date()],
            ["Customer Balance Report", "Receivables", f"{float(summary.get('receivables') or 0):,.2f}", "Multi", FinanceModel._now_date()],
            ["Supplier Balance Report", "Payables", f"{float(summary.get('payables') or 0):,.2f}", "Multi", FinanceModel._now_date()],
            ["Currency Position Report", "Net Cash", f"{float(summary.get('net_cash') or 0):,.2f}", "Multi", FinanceModel._now_date()],
            ["Cash Flow Report", "Net Cash", f"{float(summary.get('net_cash') or 0):,.2f}", "Multi", FinanceModel._now_date()],
        ]
        if keyword.strip():
            token = keyword.strip().lower()
            rows = [row for row in rows if token in row[0].lower() or token in row[1].lower()]

        self.set_table_rows(rows)
        self.set_stats(
            {
                "Cash Report": rows[0][2] if rows else "0.00",
                "Bank Report": rows[1][2] if len(rows) > 1 else "0.00",
                "Receivables": f"{float(summary.get('receivables') or 0):,.2f}",
                "Payables": f"{float(summary.get('payables') or 0):,.2f}",
            }
        )
