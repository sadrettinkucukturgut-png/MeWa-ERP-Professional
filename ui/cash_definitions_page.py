from __future__ import annotations

from PySide6.QtWidgets import QMessageBox

from models.finance_model import FinanceModel
from ui.finance_base_page import FinanceBasePage
from ui.finance_dialogs import CashAccountDialog


class CashDefinitionsPage(FinanceBasePage):
    def __init__(self):
        super().__init__(
            title="💼 Kasa Tanımları",
            layout_key="finance_cash_definitions_table",
            column_labels=[
                "Kod",
                "Kasa Adı",
                "Para Birimi",
                "Açılış Bakiyesi",
                "Sorumlu",
                "Durum",
                "Oluşturma Tarihi",
            ],
            stat_titles=["Kasa Sayısı", "Toplam Bakiye", "Aktif", "Pasif"],
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
    def _parse_notes(notes: str) -> tuple[str, str]:
        text = str(notes or "")
        responsible = ""
        status = "Aktif"
        parts = [p.strip() for p in text.split("|") if p.strip()]
        for part in parts:
            if part.lower().startswith("sorumlu:"):
                responsible = part.split(":", 1)[1].strip()
            elif part.lower().startswith("durum:"):
                status = part.split(":", 1)[1].strip() or "Aktif"
        return responsible, status

    def load_data(self, keyword: str = ""):
        rows = FinanceModel.list_cash_accounts(keyword)
        table_rows = []
        total_balance = 0.0
        active_count = 0
        passive_count = 0

        for row in rows:
            balance = float(row.get("current_balance") or 0)
            total_balance += balance
            responsible, status = self._parse_notes(str(row.get("notes") or ""))
            if status.lower() == "pasif":
                passive_count += 1
            else:
                active_count += 1

            table_rows.append(
                [
                    str(row.get("cash_code") or ""),
                    str(row.get("cash_name") or ""),
                    str(row.get("currency") or "USD"),
                    f"{float(row.get('opening_balance') or 0):,.2f}",
                    responsible,
                    status,
                    str(row.get("created_at") or ""),
                ]
            )

        self.set_table_rows(table_rows)
        self.set_stats(
            {
                "Kasa Sayısı": str(len(rows)),
                "Toplam Bakiye": f"{total_balance:,.2f}",
                "Aktif": str(active_count),
                "Pasif": str(passive_count),
            }
        )

    def _selected_cash(self) -> dict | None:
        code = str(self.selected_row_data().get("Kod") or "").strip()
        if not code:
            return None
        for row in FinanceModel.list_cash_accounts():
            if str(row.get("cash_code") or "").strip() == code:
                return row
        return None

    def _on_new(self):
        dialog = CashAccountDialog(self)
        if not dialog.exec():
            return
        payload = dialog.payload()
        try:
            FinanceModel.save_cash_account(
                cash_id=None,
                cash_code=payload.get("cash_code") or FinanceModel.next_cash_code(),
                cash_name=str(payload.get("cash_name") or ""),
                currency=str(payload.get("currency") or "USD"),
                opening_balance=float(payload.get("opening_balance") or 0),
                opening_date=str(payload.get("opening_date") or FinanceModel._now_date()),
                notes=str(payload.get("notes") or ""),
            )
            self.load_data(self.search_input.text())
        except Exception as exc:
            QMessageBox.critical(self, "Hata", str(exc))

    def _on_edit(self):
        selected = self._selected_cash()
        if selected is None:
            QMessageBox.warning(self, "Uyarı", "Lütfen bir kasa kaydı seçin.")
            return

        dialog = CashAccountDialog(self, data=selected)
        if not dialog.exec():
            return
        payload = dialog.payload()
        try:
            FinanceModel.save_cash_account(
                cash_id=int(selected.get("id") or 0),
                cash_code=str(payload.get("cash_code") or ""),
                cash_name=str(payload.get("cash_name") or ""),
                currency=str(payload.get("currency") or "USD"),
                opening_balance=float(payload.get("opening_balance") or 0),
                opening_date=str(payload.get("opening_date") or FinanceModel._now_date()),
                notes=str(payload.get("notes") or ""),
            )
            self.load_data(self.search_input.text())
        except Exception as exc:
            QMessageBox.critical(self, "Hata", str(exc))

    def _on_delete(self):
        selected = self._selected_cash()
        if selected is None:
            QMessageBox.warning(self, "Uyarı", "Lütfen bir kasa kaydı seçin.")
            return

        cash_id = int(selected.get("id") or 0)
        if FinanceModel.cash_account_has_transactions(cash_id):
            QMessageBox.warning(self, "Uyarı", "Bu kasa hareket içerdiği için silinemez.")
            return

        answer = QMessageBox.question(self, "Sil", "Seçili kasa silinsin mi?")
        if answer != QMessageBox.Yes:
            return

        try:
            FinanceModel.delete_cash_account(cash_id)
            self.load_data(self.search_input.text())
        except Exception as exc:
            QMessageBox.critical(self, "Hata", str(exc))
