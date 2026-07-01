from __future__ import annotations

from PySide6.QtWidgets import QMessageBox

from models.finance_model import FinanceModel
from ui.finance_base_page import FinanceBasePage
from ui.finance_dialogs import CollectionDialog, ExchangeRateDialog


class CustomerCollectionsPage(FinanceBasePage):
    def __init__(self):
        super().__init__(
            title="💳 Müşteri Tahsilatları",
            layout_key="finance_customer_collections_table",
            column_labels=[
                "ID",
                "Tarih",
                "Tahsilat No",
                "Müşteri",
                "Fatura",
                "Tutar",
                "Para Birimi",
                "Ödeme Yöntemi",
                "Referans",
                "Banka/Kasa",
                "Notlar",
            ],
            stat_titles=["Bugünkü Tahsilat", "Toplam Tahsilat", "Alacaklar", "Kayıt"],
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
            method = str(row.get("payment_method") or "")
            method_text = "Banka" if method == "BANK" else "Kasa" if method == "CASH" else method
            table_rows.append(
                [
                    str(row.get("id") or ""),
                    str(row.get("collection_date") or ""),
                    str(row.get("collection_no") or ""),
                    str(row.get("customer_name") or ""),
                    str(row.get("invoice_number") or ""),
                    f"{amount:,.2f}",
                    str(row.get("currency") or "USD"),
                    method_text,
                    str(row.get("reference_no") or ""),
                    str(row.get("bank_or_cash") or ""),
                    str(row.get("notes") or ""),
                ]
            )

        summary = FinanceModel.cash_flow_summary()
        self.set_table_rows(table_rows)
        self.set_stats(
            {
                "Bugünkü Tahsilat": f"{today_total:,.2f}",
                "Toplam Tahsilat": f"{total:,.2f}",
                "Alacaklar": f"{float(summary.get('receivables') or 0):,.2f}",
                "Kayıt": str(len(rows)),
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
        payload = dlg.payload()
        customer_id = int(payload.get("customer_id") or 0)
        voucher_currency = str(payload.get("currency") or "USD").strip().upper() or "USD"
        account_currency = FinanceModel.customer_account_currency(customer_id)
        exchange_rate = 1.0
        if voucher_currency != account_currency:
            exchange_rate = ExchangeRateDialog.ask_rate(
                parent=self,
                account_currency=account_currency,
                voucher_currency=voucher_currency,
            )
            if exchange_rate is None:
                return
        try:
            FinanceModel.create_customer_collection(**payload, exchange_rate=exchange_rate)
            self.load_data(self.search_input.text())
        except Exception as exc:
            QMessageBox.critical(self, "Hata", str(exc))

    def _on_edit(self):
        QMessageBox.information(self, "Bilgi", "Tahsilatlar kayıt sonrası değiştirilemez. Silip yeniden oluşturun.")

    def _on_delete(self):
        selected_id = self._selected_id()
        if selected_id <= 0:
            return
        answer = QMessageBox.question(self, "Sil", "Seçili tahsilat silinsin mi? Bu işlem bakiyeleri geri alacaktır.")
        if answer != QMessageBox.Yes:
            return
        try:
            FinanceModel.delete_customer_collection(selected_id)
            self.load_data(self.search_input.text())
        except Exception as exc:
            QMessageBox.critical(self, "Hata", str(exc))
