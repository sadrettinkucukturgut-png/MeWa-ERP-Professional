from __future__ import annotations

from models.finance_model import FinanceModel
from ui.finance_base_page import FinanceBasePage


class FinanceReportsPage(FinanceBasePage):
    def __init__(self):
        super().__init__(
            title="📈 Finans Raporları",
            layout_key="finance_reports_table",
            column_labels=["Rapor", "Metrik", "Değer", "Para Birimi", "Son Güncelleme"],
            stat_titles=["Kasa Raporu", "Banka Raporu", "Alacaklar", "Borçlar"],
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
        rows = [
            ["Kasa Raporu", "Toplam Kasa", f"{float(summary.get('total_cash') or 0):,.2f}", "Çoklu", FinanceModel._now_date()],
            ["Banka Raporu", "Toplam Banka", f"{float(summary.get('total_banks') or 0):,.2f}", "Çoklu", FinanceModel._now_date()],
            ["Tahsilat Raporu", "Bugünkü Tahsilat", f"{float(summary.get('today_collections') or 0):,.2f}", "Çoklu", FinanceModel._now_date()],
            ["Ödeme Raporu", "Bugünkü Ödeme", f"{float(summary.get('today_payments') or 0):,.2f}", "Çoklu", FinanceModel._now_date()],
            ["Alacak Yaşlandırma", "Alacaklar", f"{float(summary.get('receivables') or 0):,.2f}", "Çoklu", FinanceModel._now_date()],
            ["Borç Yaşlandırma", "Borçlar", f"{float(summary.get('payables') or 0):,.2f}", "Çoklu", FinanceModel._now_date()],
            ["Müşteri Bakiye Raporu", "Alacaklar", f"{float(summary.get('receivables') or 0):,.2f}", "Çoklu", FinanceModel._now_date()],
            ["Tedarikçi Bakiye Raporu", "Borçlar", f"{float(summary.get('payables') or 0):,.2f}", "Çoklu", FinanceModel._now_date()],
            ["Kur Pozisyon Raporu", "Net Nakit", f"{float(summary.get('net_cash') or 0):,.2f}", "Çoklu", FinanceModel._now_date()],
            ["Nakit Akış Raporu", "Net Nakit", f"{float(summary.get('net_cash') or 0):,.2f}", "Çoklu", FinanceModel._now_date()],
        ]
        if keyword.strip():
            token = keyword.strip().lower()
            rows = [row for row in rows if token in row[0].lower() or token in row[1].lower()]

        self.set_table_rows(rows)
        self.set_stats(
            {
                "Kasa Raporu": rows[0][2] if rows else "0.00",
                "Banka Raporu": rows[1][2] if len(rows) > 1 else "0.00",
                "Alacaklar": f"{float(summary.get('receivables') or 0):,.2f}",
                "Borçlar": f"{float(summary.get('payables') or 0):,.2f}",
            }
        )

    def closeEvent(self, event):  # noqa: N802
        FinanceModel.unregister_listener(self._listener)
        super().closeEvent(event)
