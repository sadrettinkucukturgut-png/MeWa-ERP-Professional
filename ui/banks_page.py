from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QDate, QEvent, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QComboBox,
    QDateEdit,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from models.finance_model import FinanceModel
from shared.widgets.action_button_bar import ActionButtonBar
from shared.widgets.cari_lookup_dialog import CariLookupDialog
from ui.finance_dialogs import ExchangeRateDialog, QuickBankDefinitionDialog
from services.document_preview_engine import DocumentLineItem, DocumentTemplate, DocumentPreviewWindow


class BanksPage(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("bankVoucherPage")
        self._last_saved: dict | None = None
        self._banks: list[dict] = []
        self._parties: list[dict] = []
        self._party_by_key: dict[tuple[str, str], dict] = {}
        self._customer_by_code: dict[str, dict] = {}
        self._customer_by_name: dict[str, dict] = {}
        self._selected_party_data: dict | None = None
        self._edit_voucher_no: str | None = None
        self._preview_windows: list[DocumentPreviewWindow] = []
        self._listener = self._on_finance_changed
        FinanceModel.register_listener(self._listener)
        self._build_ui()
        self._load_lookup_data()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(12)

        title = QLabel("🏦 Banka Transfer Fişi")
        title.setAlignment(Qt.AlignCenter)
        title.setProperty("role", "title")
        root.addWidget(title)

        card = QFrame()
        card.setProperty("card", True)
        card.setMaximumHeight(350)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 16, 16, 16)
        card_layout.setSpacing(8)

        form = QGridLayout()
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(8)

        self.transaction_date = QDateEdit()
        self.transaction_date.setCalendarPopup(True)
        self.transaction_date.setDate(QDate.currentDate())
        self.transaction_date.setMinimumHeight(36)

        self.bank_combo = QComboBox()
        self.bank_combo.setMinimumHeight(36)

        self.new_bank_button = QPushButton("Yeni Banka")
        self.new_bank_button.setMinimumHeight(36)
        self.new_bank_button.clicked.connect(self._create_new_bank)

        bank_layout = QHBoxLayout()
        bank_layout.setSpacing(8)
        bank_layout.addWidget(self.bank_combo, 1)
        bank_layout.addWidget(self.new_bank_button)
        bank_widget = QWidget()
        bank_widget.setLayout(bank_layout)

        self.customer_code_input = QLineEdit()
        self.customer_code_input.setReadOnly(True)
        self.customer_code_input.setMinimumHeight(36)
        self.customer_code_input.setPlaceholderText("Cari kodu")
        self.customer_code_input.installEventFilter(self)

        self.customer_name_input = QLineEdit()
        self.customer_name_input.setReadOnly(True)
        self.customer_name_input.setMinimumHeight(36)
        self.customer_name_input.setPlaceholderText("Cari seçmek için F4, çift tık veya ...")
        self.customer_name_input.installEventFilter(self)

        self.customer_lookup_button = QPushButton("...")
        self.customer_lookup_button.setMinimumHeight(36)
        self.customer_lookup_button.setMaximumWidth(44)
        self.customer_lookup_button.clicked.connect(self._open_cari_lookup)

        self.amount_input = QLineEdit()
        self.amount_input.setPlaceholderText("0.00")
        self.amount_input.setMinimumHeight(36)

        self.currency_combo = QComboBox()
        self.currency_combo.addItems(["TRY", "USD", "EUR"])
        self.currency_combo.setCurrentText("USD")
        self.currency_combo.setMinimumHeight(36)

        self.description_input = QTextEdit()
        self.description_input.setPlaceholderText("Transfer açıklaması")
        self.description_input.setMinimumHeight(64)
        self.description_input.setMaximumHeight(74)

        self.balance_value_label = QLabel("0.00 USD")
        self.balance_value_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.balance_value_label.setStyleSheet("font-weight:700; color:#94a3b8;")

        customer_layout = QHBoxLayout()
        customer_layout.setSpacing(8)
        customer_layout.addWidget(self.customer_code_input, 1)
        customer_layout.addWidget(self.customer_name_input, 3)
        customer_layout.addWidget(self.customer_lookup_button)
        customer_widget = QWidget()
        customer_widget.setLayout(customer_layout)

        form.addWidget(QLabel("İşlem Tarihi"), 0, 0)
        form.addWidget(self.transaction_date, 0, 1)
        form.addWidget(QLabel("Banka Seçimi"), 1, 0)
        form.addWidget(bank_widget, 1, 1)
        form.addWidget(QLabel("Müşteri"), 2, 0)
        form.addWidget(customer_widget, 2, 1)
        form.addWidget(QLabel("Cari Bakiyesi"), 3, 0)
        form.addWidget(self.balance_value_label, 3, 1)

        amount_row = QHBoxLayout()
        amount_row.setSpacing(8)
        amount_row.addWidget(self.amount_input, 1)
        amount_row.addWidget(self.currency_combo)

        form.addWidget(QLabel("Tutar"), 4, 0)
        amount_holder = QWidget()
        amount_holder.setLayout(amount_row)
        form.addWidget(amount_holder, 4, 1)

        form.addWidget(QLabel("Açıklama"), 5, 0)
        form.addWidget(self.description_input, 5, 1)

        card_layout.addLayout(form)

        self.type_group = QGroupBox("Transfer Türü")
        type_layout = QHBoxLayout(self.type_group)
        type_layout.setContentsMargins(12, 12, 12, 12)
        type_layout.setSpacing(10)

        self.incoming_btn = QPushButton("Tahsilat")
        self.incoming_btn.setCheckable(True)
        self.incoming_btn.setChecked(True)
        self.incoming_btn.setMinimumHeight(42)

        self.outgoing_btn = QPushButton("Tediye")
        self.outgoing_btn.setCheckable(True)
        self.outgoing_btn.setMinimumHeight(42)

        self.type_button_group = QButtonGroup(self)
        self.type_button_group.setExclusive(True)
        self.type_button_group.addButton(self.incoming_btn)
        self.type_button_group.addButton(self.outgoing_btn)

        type_layout.addWidget(self.incoming_btn)
        type_layout.addWidget(self.outgoing_btn)
        card_layout.addWidget(self.type_group)

        root.addWidget(card, 1)

        self.today_table = QTableWidget()
        self.today_table.setColumnCount(9)
        self.today_table.setHorizontalHeaderLabels(
            ["Tarih", "Fiş No", "Müşteri", "Açıklama", "Tahsilat/Tediye", "Tutar", "Para Birimi", "Kullanıcı", "Durum"]
        )
        self.today_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.today_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.today_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.today_table.setAlternatingRowColors(True)
        self.today_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.today_table.customContextMenuRequested.connect(self._show_today_context_menu)
        self.today_table.doubleClicked.connect(self._open_selected_voucher)
        root.addWidget(self.today_table, 1)
        root.setStretchFactor(card, 1)
        root.setStretchFactor(self.today_table, 2)

        self.action_bar = ActionButtonBar(
            self,
            include_save_close=True,
            preview_text="Önizleme",
            save_text="Kaydet",
            save_close_text="Kaydet ve Kapat",
            cancel_text="Vazgeç",
        )
        self.preview_btn = self.action_bar.preview_button
        self.save_btn = self.action_bar.save_button
        self.save_close_btn = self.action_bar.save_close_button
        self.cancel_btn = self.action_bar.cancel_button
        root.addWidget(self.action_bar)

        self.setStyleSheet(
            "QWidget#bankVoucherPage{background:#0b1220;}"
            "QLabel{color:#e2e8f0; font-size:13px;}"
            "QGroupBox{color:#e2e8f0; border:1px solid #334155; border-radius:10px; font-weight:600; margin-top:6px;}"
            "QGroupBox::title{subcontrol-origin: margin; left:10px; padding:0 4px;}"
            "QPushButton:checked{background:#1e3a8a; border:1px solid #60a5fa; color:#eff6ff; font-weight:700;}"
        )

        self.preview_btn.clicked.connect(self._open_preview)
        self.save_btn.clicked.connect(lambda: self._save(close_after=False))
        self.save_close_btn.clicked.connect(lambda: self._save(close_after=True))
        self.cancel_btn.clicked.connect(self._close_current_tab)

        self.amount_input.editingFinished.connect(self._format_amount)
        self.amount_input.returnPressed.connect(lambda: self._save(close_after=False))
        self.currency_combo.currentTextChanged.connect(lambda _v: self._update_balance_view())
        self.save_btn.setDefault(True)
        self._refresh_today_transactions()

    def _load_lookup_data(self) -> None:
        FinanceModel.ensure_default_bank_accounts()
        self._banks = FinanceModel.list_bank_accounts()
        self.bank_combo.clear()
        self.bank_combo.addItem("Banka seçiniz", None)
        for row in self._banks:
            label = f"{row.get('bank_code', '')} - {row.get('bank_name', '')} ({row.get('currency', '')})".strip()
            self.bank_combo.addItem(label, row)

        self._parties = FinanceModel.list_cari_parties()
        self._party_by_key = {}
        self._customer_by_code = {}
        self._customer_by_name = {}
        for row in self._parties:
            party_type = str(row.get("party_type") or "")
            code = str(row.get("code") or "").strip()
            name = str(row.get("name") or "").strip()
            key = (code.lower(), name.lower())
            self._party_by_key[key] = row
            if party_type == "CUSTOMER":
                if code:
                    self._customer_by_code[code.lower()] = row
                if name:
                    self._customer_by_name[name.lower()] = row

    def _create_new_bank(self) -> None:
        dialog = QuickBankDefinitionDialog(self)
        if not dialog.exec():
            return
        payload = dialog.payload()
        notes = f"Durum: {payload.get('status', 'Aktif')}"
        try:
            new_id = FinanceModel.save_bank_account(
                bank_id=None,
                bank_code=FinanceModel.next_bank_code(),
                bank_name=str(payload.get("bank_name") or "").strip(),
                branch_name=str(payload.get("branch_name") or "").strip(),
                iban=str(payload.get("iban") or "").strip(),
                swift_code="",
                account_number=str(payload.get("account_number") or "").strip(),
                currency=str(payload.get("currency") or "USD").strip().upper() or "USD",
                opening_balance=float(payload.get("opening_balance") or 0),
                opening_date=QDate.currentDate().toString("yyyy-MM-dd"),
                notes=notes,
            )
            self._load_lookup_data()
            for i in range(self.bank_combo.count()):
                row = self.bank_combo.itemData(i)
                if isinstance(row, dict) and int(row.get("id") or 0) == int(new_id):
                    self.bank_combo.setCurrentIndex(i)
                    break
        except Exception as exc:
            QMessageBox.critical(self, "Hata", f"Banka kaydedilemedi:\n{exc}")

    def _amount_value(self) -> float:
        text = str(self.amount_input.text() or "").strip()
        if not text:
            return 0.0
        normalized = text.replace(",", "")
        try:
            return float(normalized)
        except ValueError:
            return 0.0

    def _format_amount(self) -> None:
        value = self._amount_value()
        if value <= 0:
            return
        self.amount_input.setText(f"{value:,.2f}")

    def _selected_bank(self) -> dict | None:
        data = self.bank_combo.currentData()
        return data if isinstance(data, dict) else None

    def _selected_party(self) -> dict | None:
        return self._selected_party_data

    def _open_cari_lookup(self) -> None:
        selected_cari = CariLookupDialog.select_cari(self)
        if selected_cari is None:
            return
        self._apply_cari_record(selected_cari)

    def _apply_cari_record(self, record: dict) -> None:
        code = str(record.get("cari_kodu") or "").strip()
        name = str(record.get("firma_unvani") or record.get("company_name") or "").strip()
        supplier_id = int(record.get("supplier_id") or 0)

        party = None
        if supplier_id > 0:
            QMessageBox.warning(self, "Uyarı", "Bu ekranda yalnızca müşteri seçebilirsiniz.")
            return

        if code:
            party = self._customer_by_code.get(code.lower())
        if party is None and name:
            party = self._customer_by_name.get(name.lower())

        if party is None:
            QMessageBox.warning(self, "Uyarı", "Seçilen cari kaydı işlem için bulunamadı.")
            return

        self._selected_party_data = dict(party)
        customer_id = int(party.get("party_id") or 0)
        account_currency = FinanceModel.customer_account_currency(customer_id)
        self._selected_party_data["account_currency"] = account_currency
        self.customer_code_input.setText(str(party.get("code") or ""))
        self.customer_name_input.setText(str(party.get("name") or ""))

        default_currency = account_currency
        if default_currency:
            self.currency_combo.setCurrentText(default_currency)

        self._update_balance_view()
        self.raise_()
        self.activateWindow()
        self.amount_input.setFocus()

    def _update_balance_view(self) -> None:
        party = self._selected_party()
        if party is None:
            self.balance_value_label.setText(f"0.00 {self.currency_combo.currentText().strip() or 'USD'}")
            self.balance_value_label.setStyleSheet("font-weight:700; color:#94a3b8;")
            return

        customer_id = int(party.get("party_id") or 0)
        balance = FinanceModel.customer_balance(customer_id)
        currency = str(party.get("account_currency") or FinanceModel.customer_account_currency(customer_id))
        if balance > 0:
            self.balance_value_label.setText(f"{balance:,.2f} {currency} (ALACAKLIYIZ)")
            self.balance_value_label.setStyleSheet("font-weight:700; color:#16a34a;")
        elif balance < 0:
            self.balance_value_label.setText(f"{abs(balance):,.2f} {currency} (BORÇLUYUZ)")
            self.balance_value_label.setStyleSheet("font-weight:700; color:#dc2626;")
        else:
            self.balance_value_label.setText(f"BAKIYE YOK (0.00 {currency})")
            self.balance_value_label.setStyleSheet("font-weight:700; color:#94a3b8;")

    def _show_today_context_menu(self, pos):
        row = self.today_table.rowAt(pos.y())
        if row >= 0:
            self.today_table.selectRow(row)

        menu = QMenu(self)
        action_open = QAction("Open", self)
        action_edit = QAction("Edit", self)
        action_delete = QAction("Delete", self)
        action_duplicate = QAction("Duplicate", self)
        action_print = QAction("Print", self)
        action_duplicate.setEnabled(False)
        action_print.setEnabled(False)

        action_open.triggered.connect(self._open_selected_voucher)
        action_edit.triggered.connect(self._open_selected_voucher)
        action_delete.triggered.connect(self._delete_selected_voucher)

        menu.addAction(action_open)
        menu.addAction(action_edit)
        menu.addAction(action_delete)
        menu.addSeparator()
        menu.addAction(action_duplicate)
        menu.addAction(action_print)
        menu.exec_(self.today_table.viewport().mapToGlobal(pos))

    def _delete_selected_voucher(self):
        row = self.today_table.currentRow()
        if row < 0:
            return
        item = self.today_table.item(row, 0)
        payload = item.data(Qt.UserRole) if item is not None else None
        if not isinstance(payload, dict):
            return
        voucher_no = str(payload.get("voucher_no") or "").strip()
        if not voucher_no:
            return

        answer = QMessageBox.question(self, "Sil", "Bu kayıt silinsin mi?")
        if answer != QMessageBox.Yes:
            return
        try:
            FinanceModel.delete_bank_transaction(voucher_no)
            if self._edit_voucher_no == voucher_no:
                self._reset_form(keep_bank=True, keep_party=True)
            self._refresh_today_transactions()
            self._update_balance_view()
        except Exception as exc:
            QMessageBox.critical(self, "Hata", str(exc))

    def _on_finance_changed(self, _event: str) -> None:
        self._load_lookup_data()
        self._update_balance_view()
        self._refresh_today_transactions()

    def _refresh_today_transactions(self) -> None:
        rows = FinanceModel.list_today_bank_transactions(self.transaction_date.date().toString("yyyy-MM-dd"))
        self.today_table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            values = [
                str(row.get("transaction_date") or ""),
                str(row.get("voucher_no") or ""),
                str(row.get("customer_name") or ""),
                str(row.get("description") or ""),
                str(row.get("direction_text") or ""),
                f"{float(row.get('amount') or 0):,.2f}",
                str(row.get("currency") or "USD"),
                str(row.get("user") or "SYSTEM"),
                str(row.get("status") or "Posted"),
            ]
            for c, val in enumerate(values):
                item = QTableWidgetItem(val)
                if c == 5:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.today_table.setItem(r, c, item)
            first_item = self.today_table.item(r, 0)
            if first_item is not None:
                first_item.setData(Qt.UserRole, row)

    def _open_selected_voucher(self, *_args):
        row = self.today_table.currentRow()
        if row < 0:
            return
        item = self.today_table.item(row, 0)
        payload = item.data(Qt.UserRole) if item is not None else None
        if not isinstance(payload, dict):
            return
        voucher_no = str(payload.get("voucher_no") or "").strip()
        if not voucher_no:
            return
        data = FinanceModel.get_bank_transaction(voucher_no)
        if not isinstance(data, dict):
            return

        self._edit_voucher_no = voucher_no
        tx_date = QDate.fromString(str(data.get("transaction_date") or ""), "yyyy-MM-dd")
        if tx_date.isValid():
            self.transaction_date.setDate(tx_date)

        self._load_lookup_data()
        bank_id = int(data.get("bank_account_id") or 0)
        for i in range(self.bank_combo.count()):
            row_data = self.bank_combo.itemData(i)
            if isinstance(row_data, dict) and int(row_data.get("id") or 0) == bank_id:
                self.bank_combo.setCurrentIndex(i)
                break

        party_type = str(data.get("party_type") or "")
        party_id = int(data.get("party_id") or 0)
        selected = None
        for row_data in self._parties:
            if str(row_data.get("party_type") or "") == party_type and int(row_data.get("party_id") or 0) == party_id:
                selected = row_data
                break
        if selected is not None:
            self._selected_party_data = dict(selected)
            cid = int(selected.get("party_id") or 0)
            self._selected_party_data["account_currency"] = FinanceModel.customer_account_currency(cid)
            self.customer_code_input.setText(str(selected.get("code") or ""))
            self.customer_name_input.setText(str(selected.get("name") or ""))

        self.amount_input.setText(f"{float(data.get('amount') or 0):,.2f}")
        self.currency_combo.setCurrentText(str(data.get("currency") or "USD"))
        self.description_input.setPlainText(str(data.get("description") or ""))
        self.incoming_btn.setChecked(str(data.get("transfer_type") or "") == "INCOMING")
        self.outgoing_btn.setChecked(str(data.get("transfer_type") or "") == "OUTGOING")
        self._update_balance_view()

    def _resolve_exchange_rate(self, party: dict) -> float | None:
        customer_currency = str(party.get("account_currency") or "USD").strip().upper() or "USD"
        voucher_currency = self.currency_combo.currentText().strip().upper() or "USD"
        if customer_currency == voucher_currency:
            return 1.0
        return ExchangeRateDialog.ask_rate(
            parent=self,
            account_currency=customer_currency,
            voucher_currency=voucher_currency,
        )

    def _validate(self) -> bool:
        if self._selected_bank() is None:
            QMessageBox.warning(self, "Doğrulama", "Lütfen bir banka seçin.")
            return False
        if self._selected_party() is None:
            QMessageBox.warning(self, "Doğrulama", "Lütfen bir müşteri seçin.")
            return False
        if self._amount_value() <= 0:
            QMessageBox.warning(self, "Doğrulama", "Tutar 0'dan büyük olmalıdır.")
            return False
        return True

    def _transfer_type(self) -> str:
        return "INCOMING" if self.incoming_btn.isChecked() else "OUTGOING"

    def _build_template(self) -> DocumentTemplate:
        bank = self._selected_bank() or {}
        party = self._selected_party() or {}
        amount = self._amount_value()
        currency = self.currency_combo.currentText().strip() or "USD"
        tr_type = self._transfer_type()
        date_text = self.transaction_date.date().toString("yyyy-MM-dd")
        voucher_no = str((self._last_saved or {}).get("voucher_no") or "DRAFT")

        line = DocumentLineItem(
            line_no=1,
            product_code="BANK",
            description=str(self.description_input.toPlainText().strip() or "Banka transfer işlemi"),
            quantity="1",
            unit="TXN",
            unit_price=f"{amount:.2f}",
            discount="0",
            vat="0",
            total=f"{amount:.2f}",
        )

        party_name = str(party.get("name") or "")
        party_code = str(party.get("code") or "")
        notes_lines = [
            f"Fiş Numarası: {voucher_no}",
            f"Banka: {bank.get('bank_name', '')}",
            f"İşlem Türü: {'Tahsilat' if tr_type == 'INCOMING' else 'Tediye'}",
            f"Cari: {party_code} - {party_name}".strip(" -"),
            f"Para Birimi: {currency}",
            f"Tutar: {amount:,.2f}",
            "İmza: __________________________",
        ]

        return DocumentTemplate(
            document_title="BANKA TRANSFER FİŞİ",
            filename_base=f"bank_voucher_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            invoice_number=voucher_no,
            invoice_date=date_text,
            due_date=date_text,
            currency=currency,
            customer_name=party_name,
            customer_company_name=party_name,
            customer_code=party_code,
            customer_phone="",
            customer_email="",
            subtotal=f"{amount:.2f}",
            discount_total="0.00",
            vat_total="0.00",
            grand_total=f"{amount:.2f}",
            notes="\n".join(notes_lines),
            items=[line],
        )

    def _open_preview(self) -> None:
        if not self._validate():
            return
        preview = DocumentPreviewWindow(template=self._build_template(), parent=self)
        self._preview_windows.append(preview)
        preview.show()
        preview.raise_()
        preview.activateWindow()

    def _save(self, *, close_after: bool) -> bool:
        if not self._validate():
            return False

        bank = self._selected_bank() or {}
        party = self._selected_party() or {}
        exchange_rate = self._resolve_exchange_rate(party)
        if exchange_rate is None:
            return False
        try:
            payload = {
                "transaction_date": self.transaction_date.date().toString("yyyy-MM-dd"),
                "bank_account_id": int(bank.get("id") or 0),
                "transfer_type": self._transfer_type(),
                "party_type": str(party.get("party_type") or ""),
                "party_id": int(party.get("party_id") or 0),
                "amount": self._amount_value(),
                "currency": self.currency_combo.currentText().strip() or "USD",
                "description": self.description_input.toPlainText().strip(),
                "exchange_rate": exchange_rate,
            }
            if self._edit_voucher_no:
                result = FinanceModel.update_bank_transaction(voucher_no=self._edit_voucher_no, **payload)
            else:
                result = FinanceModel.create_bank_transaction(**payload)
            self._last_saved = result
            QMessageBox.information(
                self,
                "Başarılı",
                f"Banka işlemi kaydedildi.\nFiş: {result.get('voucher_no', '')}\nKalan Bakiye: {float(result.get('balance_after') or 0):,.2f}",
            )
            if close_after:
                self._close_current_tab()
            else:
                self._reset_form(keep_bank=True, keep_party=True)
            self._edit_voucher_no = None
            self._refresh_today_transactions()
            self._update_balance_view()
            return True
        except Exception as exc:
            QMessageBox.critical(self, "Hata", f"Banka işlemi kaydedilemedi:\n{exc}")
            return False

    def _reset_form(self, keep_bank: bool = False, keep_party: bool = False) -> None:
        self._edit_voucher_no = None
        keep_bank_index = self.bank_combo.currentIndex() if keep_bank else 0
        selected_party = dict(self._selected_party_data) if keep_party and self._selected_party_data else None
        self.transaction_date.setDate(QDate.currentDate())
        self.incoming_btn.setChecked(True)
        self.amount_input.clear()
        self.currency_combo.setCurrentText("USD")
        self.description_input.clear()
        self.bank_combo.setCurrentIndex(max(0, keep_bank_index))
        if selected_party is not None:
            self._selected_party_data = selected_party
            self.customer_code_input.setText(str(selected_party.get("code") or ""))
            self.customer_name_input.setText(str(selected_party.get("name") or ""))
        else:
            self._selected_party_data = None
            self.customer_code_input.clear()
            self.customer_name_input.clear()
        self._update_balance_view()
        self._refresh_today_transactions()

    def eventFilter(self, watched, event):  # noqa: N802
        if watched in (self.customer_code_input, self.customer_name_input) and event.type() == QEvent.MouseButtonDblClick:
            self._open_cari_lookup()
            return True
        return super().eventFilter(watched, event)

    def keyPressEvent(self, event):  # noqa: N802
        if event.key() == Qt.Key_F4 and self.focusWidget() in (self.customer_code_input, self.customer_name_input):
            self._open_cari_lookup()
            return
        super().keyPressEvent(event)

    def _close_current_tab(self) -> None:
        parent = self.parentWidget()
        while parent is not None:
            if parent.__class__.__name__ == "TabManager":
                index = parent.indexOf(self)
                if index >= 0:
                    parent.removeTab(index)
                return
            parent = parent.parentWidget()

    def closeEvent(self, event):  # noqa: N802
        FinanceModel.unregister_listener(self._listener)
        super().closeEvent(event)
