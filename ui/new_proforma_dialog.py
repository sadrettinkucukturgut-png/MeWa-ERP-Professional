import os
from typing import Any, Dict, List, Optional

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import QMessageBox, QPushButton

from models.proforma_model import ProformaModel
from services.proforma_conversion_service import ProformaConversionService
from services.document_preview_engine import (
    DocumentLineItem,
    DocumentTemplate,
    ProformaTemplateBuilder,
    build_template_signature,
    resolve_party_details,
)
from ui.new_export_sales_invoice_dialog import NewExportSalesInvoiceDialog


class NewProformaDialog(NewExportSalesInvoiceDialog):
    def __init__(self, invoice_number: Optional[str] = None, parent=None):
        super().__init__(invoice_number=invoice_number, parent=parent)
        self.setWindowTitle("Proforma Düzenle" if self.is_edit_mode else "Yeni Proforma")
        self.convert_btn = QPushButton("Convert to Export Sales Invoice")
        self.convert_btn.clicked.connect(self._on_convert_to_export_sales_invoice)
        self._attach_conversion_button_to_row()
        if not self.is_edit_mode:
            self.invoice_number_input.setText(ProformaModel.invoice_number_generate())
        self._refresh_conversion_state()

    def _attach_conversion_button_to_row(self) -> None:
        content = self.scroll_area.widget() if hasattr(self, "scroll_area") else None
        if content is None or content.layout() is None:
            return
        parent_layout = content.layout()
        for i in range(parent_layout.count()):
            item = parent_layout.itemAt(i)
            row_layout = item.layout() if item is not None else None
            if row_layout is None:
                continue
            if row_layout.indexOf(self.preview_btn) >= 0:
                row_layout.insertWidget(1, self.convert_btn)
                return

    def _validate_before_save(self) -> Optional[str]:
        invoice_number = self.invoice_number_input.text().strip()
        if not invoice_number:
            return "Proforma No boş olamaz."

        if not self.cari_input.text().strip():
            return "Cari seçimi zorunludur."

        has_stock_line = False
        for row in range(self.product_table.rowCount()):
            stock_code_item = self.product_table.item(row, self.COL_STOCK_CODE)
            qty = self._cell_float(row, self.COL_QTY, 0)
            if stock_code_item is None or not stock_code_item.text().strip():
                continue
            if qty <= 0:
                return f"{row + 1}. satırdaki miktar 0'dan büyük olmalıdır."
            has_stock_line = True

        if not has_stock_line:
            return "En az bir stok satırı girilmelidir."

        existing = ProformaModel.invoice_detail(invoice_number)
        if existing is not None and not (self.is_edit_mode and invoice_number == self.invoice_number):
            return "Bu proforma numarası zaten kullanılıyor."

        return None

    def _load_invoice(self, invoice_number: str):
        invoice = ProformaModel.invoice_detail(invoice_number)
        if invoice is None:
            QMessageBox.warning(self, "Uyarı", "Proforma bulunamadı.")
            self.reject()
            return

        self.invoice_number_input.setText(str(invoice.get("invoice_number") or ""))
        customer_record = {
            "customer_id": int(invoice.get("customer_id") or 0),
            "supplier_id": int(invoice.get("customer_id") or 0),
            "cari_kodu": str(invoice.get("customer_code") or ""),
            "firma_unvani": str(invoice.get("customer_name") or ""),
            "payment_term": "",
            "default_currency": str(invoice.get("currency") or "USD"),
        }
        self._apply_cari_record(customer_record)

        invoice_date = QDate.fromString(str(invoice.get("invoice_date") or ""), "yyyy-MM-dd")
        if invoice_date.isValid():
            self.invoice_date_input.setDate(invoice_date)

        due_date = QDate.fromString(str(invoice.get("due_date") or ""), "yyyy-MM-dd")
        if due_date.isValid():
            self.due_date_input.setDate(due_date)

        self.currency_combo.setCurrentText(str(invoice.get("currency") or "USD"))
        self.exchange_rate_input.setValue(float(invoice.get("exchange_rate") or 1.0))
        self.notes_input.setPlainText(str(invoice.get("notes") or ""))
        self.payment_term_input.setText(str(invoice.get("payment_terms") or ""))

        self.product_table.blockSignals(True)
        self.product_table.setRowCount(0)
        for item in invoice.get("items", []):
            self._append_item_row(
                goods_receipt_item_id=0,
                stock_id=int(item.get("stock_id") or 0),
                stock_code=str(item.get("stock_code") or ""),
                product_name=str(item.get("product_name") or ""),
                qty=float(item.get("quantity") or 0),
                unit=str(item.get("unit") or ""),
                unit_price=float(item.get("unit_price") or 0),
                discount=float(item.get("discount_percent") or 0),
                vat=float(item.get("vat_percent") or 0),
            )
        self.product_table.blockSignals(False)
        if self.product_table.rowCount() == 0:
            self._add_product_row()
        self._sync_table_height()
        self._update_totals()
        self._refresh_conversion_state()

    def _refresh_conversion_state(self) -> None:
        invoice_no = self.invoice_number_input.text().strip()
        info = ProformaModel.conversion_info(invoice_no) if invoice_no else None
        if info is None:
            self.convert_btn.setEnabled(False)
            self.convert_btn.setToolTip("Save the Proforma before converting.")
            return

        if bool(info.get("is_converted")):
            converted_no = str(info.get("converted_invoice_number") or "")
            self.convert_btn.setEnabled(False)
            self.convert_btn.setToolTip(
                f"Already converted to Export Sales Invoice {converted_no}."
            )
            return

        if not bool(info.get("can_convert")):
            self.convert_btn.setEnabled(False)
            self.convert_btn.setToolTip("This Proforma cannot be converted in its current status.")
            return

        self.convert_btn.setEnabled(True)
        self.convert_btn.setToolTip("Convert this Proforma into Export Sales Invoice")

    def _on_convert_to_export_sales_invoice(self) -> None:
        if not self._has_persisted_document:
            if not self._save_document(close_on_success=False):
                return
        elif self._has_unsaved_changes():
            answer = QMessageBox.question(
                self,
                "Unsaved Changes",
                "Document has unsaved changes. Save before conversion?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes,
            )
            if answer != QMessageBox.Yes:
                return
            if not self._save_document(close_on_success=False):
                return

        proforma_no = self.invoice_number_input.text().strip()
        info = ProformaModel.conversion_info(proforma_no)
        if info is None:
            QMessageBox.warning(self, "Warning", "Proforma could not be found.")
            return
        if bool(info.get("is_converted")):
            converted_no = str(info.get("converted_invoice_number") or "")
            QMessageBox.warning(
                self,
                "Already Converted",
                f"This Proforma has already been converted into Export Sales Invoice {converted_no}.",
            )
            self._refresh_conversion_state()
            return

        confirm = QMessageBox.question(
            self,
            "Convert Proforma",
            "This action will convert this Proforma to Export Sales Invoice and can only be performed once. Continue?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return

        created_by = os.getenv("USERNAME") or os.getenv("USER") or "SYSTEM"
        try:
            result = ProformaConversionService.convert_to_export_sales_invoice(proforma_no, created_by=created_by)
            QMessageBox.information(
                self,
                "Conversion Completed",
                (
                    f"Proforma {result.get('proforma_number')} converted successfully.\n"
                    f"New Export Sales Invoice: {result.get('sales_invoice_number')}"
                ),
            )
            self._load_invoice(proforma_no)
        except Exception as exc:
            QMessageBox.warning(self, "Conversion Failed", str(exc))
        finally:
            self._refresh_conversion_state()

    def _save_document(self, close_on_success: bool) -> bool:
        validation_error = self._validate_before_save()
        if validation_error:
            QMessageBox.warning(self, "Uyarı", validation_error)
            return False

        entered_invoice_number = self.invoice_number_input.text().strip()

        customer_id = int(self._selected_cari_record.get("customer_id") or 0) if self._selected_cari_record else 0
        customer_id = ProformaModel.resolve_or_create_customer_id(
            customer_id=customer_id,
            cari_kodu=str(self.cari_kodu_input.text().strip()),
            firma_unvani=str(self.company_name_input.text().strip() or self.cari_input.text().strip()),
            default_currency=str(self.currency_combo.currentText().strip() or "USD"),
        )
        if customer_id <= 0:
            QMessageBox.warning(self, "Uyarı", "Cari bilgisi geçerli değil.")
            return False

        items: List[Dict[str, Any]] = []
        for row in range(self.product_table.rowCount()):
            stock_code_item = self.product_table.item(row, self.COL_STOCK_CODE)
            if stock_code_item is None or not stock_code_item.text().strip():
                continue
            qty = self._cell_float(row, self.COL_QTY, 0)
            if qty <= 0:
                continue

            items.append(
                {
                    "stock_id": int(stock_code_item.data(Qt.UserRole + 1) or 0),
                    "quantity": qty,
                    "unit": self.product_table.item(row, self.COL_UNIT).text().strip() if self.product_table.item(row, self.COL_UNIT) else "",
                    "unit_price": self._cell_float(row, self.COL_UNIT_PRICE, 0),
                    "discount_percent": self._cell_float(row, self.COL_DISCOUNT, 0),
                    "vat_percent": self._cell_float(row, self.COL_VAT, 0),
                }
            )

        if not items:
            QMessageBox.warning(self, "Uyarı", "En az bir stok satırı girilmelidir.")
            return False

        created_by = os.getenv("USERNAME") or os.getenv("USER") or "SYSTEM"
        current_status = "Draft"
        if self.is_edit_mode and self.invoice_number:
            existing_detail = ProformaModel.invoice_detail(self.invoice_number)
            if existing_detail is not None:
                current_status = str(existing_detail.get("status") or "Draft")

        try:
            ProformaModel.save_invoice(
                invoice_number=entered_invoice_number,
                customer_id=customer_id,
                invoice_date=self.invoice_date_input.date().toString("yyyy-MM-dd"),
                due_date=self.due_date_input.date().toString("yyyy-MM-dd"),
                currency=self.currency_combo.currentText(),
                exchange_rate=float(self.exchange_rate_input.value()),
                notes=self.notes_input.toPlainText().strip(),
                payment_terms=self.payment_term_input.text().strip(),
                delivery_terms="",
                items=items,
                created_by=created_by,
                existing_invoice_number=self.invoice_number if self.is_edit_mode else None,
                status=current_status,
            )
            self.saved_invoice_number = self.invoice_number_input.text().strip()
            self.invoice_number = entered_invoice_number
            self.is_edit_mode = True
            self._has_persisted_document = True
            self.preview_btn.setEnabled(True)
            self._last_saved_signature = build_template_signature(self._build_preview_template())
            if not close_on_success:
                QMessageBox.information(self, "Bilgi", "Proforma başarıyla kaydedildi.")
            if close_on_success:
                self.accept()
            self._refresh_conversion_state()
            return True
        except Exception as exc:
            QMessageBox.critical(self, "Hata", f"Proforma kaydedilemedi:\n{exc}")
            return False

    def _build_preview_template(self) -> DocumentTemplate:
        customer_name = self.company_name_input.text().strip() or self.cari_input.text().strip()
        customer_code = self.cari_kodu_input.text().strip()
        party = resolve_party_details(party_code=customer_code, party_name=customer_name)

        items: list[DocumentLineItem] = []
        subtotal = 0.0
        discount_total = 0.0
        vat_total = 0.0

        for row in range(self.product_table.rowCount()):
            stock_code_item = self.product_table.item(row, self.COL_STOCK_CODE)
            if stock_code_item is None or not stock_code_item.text().strip():
                continue

            qty = self._cell_float(row, self.COL_QTY, 0)
            unit_price = self._cell_float(row, self.COL_UNIT_PRICE, 0)
            discount_percent = self._cell_float(row, self.COL_DISCOUNT, 0)
            vat_percent = self._cell_float(row, self.COL_VAT, 0)

            base = qty * unit_price
            disc = base * (discount_percent / 100.0)
            net = base - disc
            vat_amount = net * (vat_percent / 100.0)
            line_total = net + vat_amount

            subtotal += base
            discount_total += disc
            vat_total += vat_amount

            product = self.product_table.item(row, self.COL_PRODUCT).text().strip() if self.product_table.item(row, self.COL_PRODUCT) else ""
            unit = self.product_table.item(row, self.COL_UNIT).text().strip() if self.product_table.item(row, self.COL_UNIT) else ""

            items.append(
                DocumentLineItem(
                    line_no=len(items) + 1,
                    product_code=stock_code_item.text().strip(),
                    description=product,
                    quantity=f"{qty:.3f}".rstrip("0").rstrip("."),
                    unit=unit,
                    unit_price=f"{unit_price:.2f}",
                    discount=f"{discount_percent:.2f}",
                    vat=f"{vat_percent:.2f}%",
                    total=f"{line_total:.2f}",
                    amount=f"{line_total:.2f}",
                )
            )

        grand_total = subtotal - discount_total + vat_total
        notes = self.notes_input.toPlainText().strip()
        return DocumentTemplate(
            document_title="PROFORMA INVOICE",
            filename_base=(self.invoice_number_input.text().strip() or "proforma").replace("/", "-"),
            document_kind="PROFORMA",
            invoice_number=self.invoice_number_input.text().strip(),
            invoice_date=self.invoice_date_input.date().toString("yyyy-MM-dd"),
            due_date=self.due_date_input.date().toString("yyyy-MM-dd"),
            expiry_date=self.due_date_input.date().toString("yyyy-MM-dd"),
            currency=self.currency_combo.currentText().strip() or "USD",
            exchange_rate=str(self.exchange_rate_input.value()),
            customer_name=party.get("name") or customer_name,
            customer_company_name=party.get("name") or customer_name,
            customer_address=party.get("address") or "",
            customer_country=party.get("country") or "",
            customer_tax_number=party.get("tax_number") or "",
            customer_phone=party.get("phone") or "",
            customer_email=party.get("email") or "",
            customer_code=customer_code,
            customer_whatsapp=party.get("phone") or "",
            bill_to_company=party.get("name") or customer_name,
            bill_to_address=party.get("address") or "",
            bill_to_country=party.get("country") or "",
            bill_to_contact=party.get("name") or customer_name,
            bill_to_phone=party.get("phone") or "",
            bill_to_email=party.get("email") or "",
            bill_to_tax_number=party.get("tax_number") or "",
            ship_to_company=party.get("name") or customer_name,
            ship_to_address=party.get("address") or "",
            ship_to_country=party.get("country") or "",
            ship_to_contact=party.get("name") or customer_name,
            ship_to_phone=party.get("phone") or "",
            ship_to_email=party.get("email") or "",
            ship_to_tax_number=party.get("tax_number") or "",
            subtotal=f"{subtotal:.2f}",
            discount_percent="0.00",
            discount_total=f"{discount_total:.2f}",
            net_total=f"{(subtotal - discount_total):.2f}",
            vat_total=f"{vat_total:.2f}",
            grand_total=f"{grand_total:.2f}",
            notes=notes,
            terms_conditions=notes,
            payment_terms=self.payment_term_input.text().strip(),
            delivery_terms="",
            items=items,
        )

    def _build_saved_preview_template(self) -> DocumentTemplate:
        invoice_no = self.invoice_number_input.text().strip()
        if not invoice_no:
            return self._build_preview_template()

        proforma_template = ProformaTemplateBuilder.from_saved_proforma_number(invoice_no)
        if proforma_template is not None:
            return proforma_template

        invoice = ProformaModel.invoice_detail(invoice_no)
        if invoice is None:
            return self._build_preview_template()

        return self._build_preview_template()
