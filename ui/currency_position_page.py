from __future__ import annotations

from models.finance_model import FinanceModel
from ui.finance_base_page import FinanceBasePage


class CurrencyPositionPage(FinanceBasePage):
    def __init__(self):
        super().__init__(
            title="💱 Kur Pozisyonu",
            layout_key="finance_currency_position_table",
            column_labels=[
                "Para Birimi",
                "Kasa",
                "Banka",
                "Alacak",
                "Borç",
                "Toplam Varlık",
                "Toplam Yükümlülük",
                "Net Pozisyon",
                "Ortalama Kur",
                "Bugünkü Kur",
                "Fark",
            ],
            stat_titles=["TRY Net", "USD Net", "EUR Net", "Toplam Net"],
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
        rows = FinanceModel.currency_position()
        table_rows = []
        total_net = 0.0
        net_map = {"TRY": 0.0, "USD": 0.0, "EUR": 0.0}

        for row in rows:
            code = str(row.get("currency") or "")
            net = float(row.get("net_position") or 0)
            net_map[code] = net
            total_net += net
            table_rows.append(
                [
                    code,
                    f"{float(row.get('cash') or 0):,.2f}",
                    f"{float(row.get('bank') or 0):,.2f}",
                    f"{float(row.get('receivable') or 0):,.2f}",
                    f"{float(row.get('payable') or 0):,.2f}",
                    f"{float(row.get('total_assets') or 0):,.2f}",
                    f"{float(row.get('total_liabilities') or 0):,.2f}",
                    f"{net:,.2f}",
                    f"{float(row.get('avg_exchange_rate') or 0):,.4f}",
                    f"{float(row.get('today_rate') or 0):,.4f}",
                    f"{float(row.get('difference') or 0):,.4f}",
                ]
            )

        if keyword.strip():
            token = keyword.strip().upper()
            table_rows = [row for row in table_rows if token in row[0].upper()]

        self.set_table_rows(table_rows)
        self.set_stats(
            {
                "TRY Net": f"{net_map.get('TRY', 0.0):,.2f}",
                "USD Net": f"{net_map.get('USD', 0.0):,.2f}",
                "EUR Net": f"{net_map.get('EUR', 0.0):,.2f}",
                "Toplam Net": f"{total_net:,.2f}",
            }
        )

    def closeEvent(self, event):  # noqa: N802
        FinanceModel.unregister_listener(self._listener)
        super().closeEvent(event)
