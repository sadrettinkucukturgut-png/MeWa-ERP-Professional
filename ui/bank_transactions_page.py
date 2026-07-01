from __future__ import annotations

from models.finance_model import FinanceModel
from ui.finance_base_page import FinanceBasePage


class BankTransactionsPage(FinanceBasePage):
    def __init__(self):
        super().__init__(
            title="📒 Banka Hareketleri",
            layout_key="finance_bank_transactions_table",
            column_labels=[
                "Tarih",
                "İşlem No",
                "Hesap",
                "Açıklama",
                "Para Birimi",
                "Borç",
                "Alacak",
                "Bakiye",
                "Referans",
                "Belge",
                "Kümülatif Bakiye",
            ],
            stat_titles=["Toplam Borç", "Toplam Alacak", "Net Hareket", "Kayıt"],
        )
        self.action_new.setEnabled(False)
        self.action_edit.setEnabled(False)
        self.action_delete.setEnabled(False)
        self.load_data()

    def load_data(self, keyword: str = ""):
        rows = FinanceModel.list_bank_transactions(keyword)
        table_rows = []
        total_debit = 0.0
        total_credit = 0.0
        for row in rows:
            debit = float(row.get("debit") or 0)
            credit = float(row.get("credit") or 0)
            balance = debit - credit
            running = float(row.get("running_balance") or 0)
            total_debit += debit
            total_credit += credit
            table_rows.append(
                [
                    str(row.get("transaction_date") or ""),
                    str(row.get("transaction_no") or ""),
                    str(row.get("account_name") or ""),
                    str(row.get("description") or ""),
                    str(row.get("currency") or "USD"),
                    f"{debit:,.2f}",
                    f"{credit:,.2f}",
                    f"{balance:,.2f}",
                    str(row.get("reference_no") or ""),
                    str(row.get("document_no") or ""),
                    f"{running:,.2f}",
                ]
            )
        self.set_table_rows(table_rows)
        self.set_stats(
            {
                "Toplam Borç": f"{total_debit:,.2f}",
                "Toplam Alacak": f"{total_credit:,.2f}",
                "Net Hareket": f"{(total_debit - total_credit):,.2f}",
                "Kayıt": str(len(rows)),
            }
        )
