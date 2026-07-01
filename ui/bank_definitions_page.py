from __future__ import annotations

from PySide6.QtWidgets import QMessageBox

from models.finance_model import FinanceModel
from ui.finance_base_page import FinanceBasePage
from ui.finance_dialogs import BankAccountDialog


class BankDefinitionsPage(FinanceBasePage):
    def __init__(self):
        super().__init__(
            title="🏛 Banka Tanımları",
            layout_key="finance_bank_definitions_table",
            column_labels=[
                "Banka Kodu",
                "Banka Adı",
                "Şube",
                "IBAN",
                "Hesap No",
                "Para Birimi",
                "Açılış Bakiyesi",
                "Durum",
            ],
            stat_titles=["Banka Sayısı", "Toplam Bakiye", "Aktif", "Pasif"],
        )
        for action in list(self.toolbar.actions()):
            self.toolbar.removeAction(action)
        for action in [
            self.action_new,
            self.action_edit,
            self.action_delete,
            self.action_refresh,
            self.action_excel,
            self.action_pdf,
            self.action_print,
            self.action_search,
            self.action_columns,
        ]:
            self.toolbar.addAction(action)
        self.load_data()

    @staticmethod
    def _status_from_notes(notes: str) -> str:
        text = str(notes or "")
        for part in [p.strip() for p in text.split("|") if p.strip()]:
            if part.lower().startswith("durum:"):
                return part.split(":", 1)[1].strip() or "Aktif"
        return "Aktif"

    def load_data(self, keyword: str = ""):
        rows = FinanceModel.list_bank_accounts(keyword)
        table_rows = []
        total_balance = 0.0
        active_count = 0
        passive_count = 0

        for row in rows:
            status = self._status_from_notes(str(row.get("notes") or ""))
            if status.lower() == "pasif":
                passive_count += 1
            else:
                active_count += 1
            total_balance += float(row.get("current_balance") or 0)
            table_rows.append(
                [
                    str(row.get("bank_code") or ""),
                    str(row.get("bank_name") or ""),
                    str(row.get("branch_name") or ""),
                    str(row.get("iban") or ""),
                    str(row.get("account_number") or ""),
                    str(row.get("currency") or "USD"),
                    f"{float(row.get('opening_balance') or 0):,.2f}",
                    status,
                ]
            )

        self.set_table_rows(table_rows)
        self.set_stats(
            {
                "Banka Sayısı": str(len(rows)),
                "Toplam Bakiye": f"{total_balance:,.2f}",
                "Aktif": str(active_count),
                "Pasif": str(passive_count),
            }
        )

    def _selected_bank(self) -> dict | None:
        code = str(self.selected_row_data().get("Banka Kodu") or "").strip()
        if not code:
            return None
        for row in FinanceModel.list_bank_accounts():
            if str(row.get("bank_code") or "").strip() == code:
                return row
        return None

    def _on_new(self):
        dialog = BankAccountDialog(self)
        if not dialog.exec():
            return
        payload = dialog.payload()
        try:
            FinanceModel.save_bank_account(
                bank_id=None,
                bank_code=str(payload.get("bank_code") or FinanceModel.next_bank_code()),
                bank_name=str(payload.get("bank_name") or ""),
                branch_name=str(payload.get("branch_name") or ""),
                iban=str(payload.get("iban") or ""),
                swift_code=str(payload.get("swift_code") or ""),
                account_number=str(payload.get("account_number") or ""),
                currency=str(payload.get("currency") or "USD"),
                opening_balance=float(payload.get("opening_balance") or 0),
                opening_date=str(payload.get("opening_date") or FinanceModel._now_date()),
                notes=str(payload.get("notes") or ""),
            )
            self.load_data(self.search_input.text())
        except Exception as exc:
            QMessageBox.critical(self, "Hata", str(exc))

    def _on_edit(self):
        selected = self._selected_bank()
        if selected is None:
            QMessageBox.warning(self, "Uyarı", "Lütfen bir banka kaydı seçin.")
            return

        dialog = BankAccountDialog(self, data=selected)
        if not dialog.exec():
            return
        payload = dialog.payload()
        try:
            FinanceModel.save_bank_account(
                bank_id=int(selected.get("id") or 0),
                bank_code=str(payload.get("bank_code") or ""),
                bank_name=str(payload.get("bank_name") or ""),
                branch_name=str(payload.get("branch_name") or ""),
                iban=str(payload.get("iban") or ""),
                swift_code=str(payload.get("swift_code") or ""),
                account_number=str(payload.get("account_number") or ""),
                currency=str(payload.get("currency") or "USD"),
                opening_balance=float(payload.get("opening_balance") or 0),
                opening_date=str(payload.get("opening_date") or FinanceModel._now_date()),
                notes=str(payload.get("notes") or ""),
            )
            self.load_data(self.search_input.text())
        except Exception as exc:
            QMessageBox.critical(self, "Hata", str(exc))

    def _on_delete(self):
        selected = self._selected_bank()
        if selected is None:
            QMessageBox.warning(self, "Uyarı", "Lütfen bir banka kaydı seçin.")
            return

        bank_id = int(selected.get("id") or 0)
        if FinanceModel.bank_account_has_transactions(bank_id):
            QMessageBox.warning(self, "Uyarı", "Bu banka hareket içerdiği için silinemez.")
            return

        answer = QMessageBox.question(self, "Sil", "Seçili banka silinsin mi?")
        if answer != QMessageBox.Yes:
            return

        try:
            FinanceModel.delete_bank_account(bank_id)
            self.load_data(self.search_input.text())
        except Exception as exc:
            QMessageBox.critical(self, "Hata", str(exc))
