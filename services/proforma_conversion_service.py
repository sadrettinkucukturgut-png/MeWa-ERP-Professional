from typing import Any, Dict

from models.export_sales_invoice_model import ExportSalesInvoiceModel
from models.proforma_model import ProformaModel


class ProformaConversionService:
    @staticmethod
    def convert_to_export_sales_invoice(proforma_number: str, created_by: str = "SYSTEM") -> Dict[str, Any]:
        proforma = ProformaModel.invoice_detail(proforma_number)
        if proforma is None:
            raise ValueError("Proforma not found")

        existing_invoice = str(proforma.get("converted_invoice_number") or "").strip()
        if existing_invoice:
            raise ValueError(
                f"This Proforma has already been converted into Export Sales Invoice {existing_invoice}."
            )

        status = str(proforma.get("status") or "Draft").strip().lower()
        if status in ("cancelled", "rejected"):
            raise ValueError("Rejected or cancelled Proforma cannot be converted.")

        items = []
        for line in proforma.get("items", []):
            qty = float(line.get("quantity") or 0)
            if qty <= 0:
                continue
            items.append(
                {
                    "stock_id": int(line.get("stock_id") or 0),
                    "quantity": qty,
                    "unit": str(line.get("unit") or ""),
                    "unit_price": float(line.get("unit_price") or 0),
                    "discount_percent": float(line.get("discount_percent") or 0),
                    "vat_percent": float(line.get("vat_percent") or 0),
                }
            )

        if not items:
            raise ValueError("Proforma has no valid line items for conversion.")

        new_invoice_number = ExportSalesInvoiceModel.invoice_number_generate()
        ExportSalesInvoiceModel.save_invoice(
            invoice_number=new_invoice_number,
            customer_id=int(proforma.get("customer_id") or 0),
            invoice_date=str(proforma.get("invoice_date") or ""),
            due_date=str(proforma.get("due_date") or ""),
            currency=str(proforma.get("currency") or "USD"),
            exchange_rate=float(proforma.get("exchange_rate") or 1),
            notes=str(proforma.get("notes") or ""),
            items=items,
            created_by=created_by,
            source_proforma_number=str(proforma.get("invoice_number") or ""),
            payment_terms=str(proforma.get("payment_terms") or ""),
            delivery_terms=str(proforma.get("delivery_terms") or ""),
        )

        ProformaModel.mark_converted(
            invoice_number=str(proforma.get("invoice_number") or proforma_number),
            sales_invoice_number=new_invoice_number,
            created_by=created_by,
        )

        return {
            "proforma_number": str(proforma.get("invoice_number") or proforma_number),
            "sales_invoice_number": new_invoice_number,
            "status": "Converted",
        }
