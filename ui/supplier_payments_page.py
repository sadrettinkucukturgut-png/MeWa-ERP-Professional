from __future__ import annotations

from PySide6.QtWidgets import QMessageBox

from models.finance_model import FinanceModel
from ui.finance_base_page import FinanceBasePage
from ui.finance_dialogs import ExchangeRateDialog, SupplierPaymentDialog


class SupplierPaymentsPage(FinanceBasePage):
    def __init__(self):
        super().__init__(
            title="💸 Tedarikçi Ödemeleri",
            layout_key="finance_supplier_payments_table",
            column_labels=[
                "ID",
                "Tarih",
                "Ödeme No",
                "Tedarikçi",
                "Alış Faturası",
                "Tutar",
                "Para Birimi",
                "Ödeme Yöntemi",
                "Referans",
                "Banka/Kasa",
                "Notlar",
            ],
            stat_titles=["Bugünkü Ödeme", "Toplam Ödeme", "Borçlar", "Kayıt"],
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
            method = str(row.get("payment_method") or "")
            method_text = "Banka" if method == "BANK" else "Kasa" if method == "CASH" else method
            table_rows.append(
                [
                    str(row.get("id") or ""),
                    str(row.get("payment_date") or ""),
                    str(row.get("payment_no") or ""),
                    str(row.get("supplier_name") or ""),
                    str(row.get("purchase_invoice_number") or ""),
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
                "Bugünkü Ödeme": f"{today_total:,.2f}",
                "Toplam Ödeme": f"{total:,.2f}",
                "Borçlar": f"{float(summary.get('payables') or 0):,.2f}",
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
        dlg = SupplierPaymentDialog(
            parent=self,
            suppliers=FinanceModel.list_suppliers(),
            banks=FinanceModel.list_bank_accounts(),
            cash_accounts=FinanceModel.list_cash_accounts(),
        )
        if not dlg.exec():
            return
        payload = dlg.payload()
        supplier_id = int(payload.get("supplier_id") or 0)
        voucher_currency = str(payload.get("currency") or "USD").strip().upper() or "USD"
        account_currency = FinanceModel.supplier_account_currency(supplier_id)
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
            FinanceModel.create_supplier_payment(**payload, exchange_rate=exchange_rate)
            self.load_data(self.search_input.text())
        except Exception as exc:
            QMessageBox.critical(self, "Hata", str(exc))

    def _on_edit(self):
        QMessageBox.information(self, "Bilgi", "Ödemeler kayıt sonrası değiştirilemez. Silip yeniden oluşturun.")

    def _on_delete(self):
        selected_id = self._selected_id()
        if selected_id <= 0:
            return
        answer = QMessageBox.question(self, "Sil", "Seçili ödeme silinsin mi? Bu işlem bakiyeleri geri alacaktır.")
        if answer != QMessageBox.Yes:
            return
        try:
            FinanceModel.delete_supplier_payment(selected_id)
            self.load_data(self.search_input.text())
        except Exception as exc:
            QMessageBox.critical(self, "Hata", str(exc))
