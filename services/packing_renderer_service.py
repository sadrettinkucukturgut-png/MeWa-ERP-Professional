from __future__ import annotations

from typing import List, Optional

from models.packing_model import PackingItem
from services.document_preview_engine import DocumentLineItem, DocumentTemplate


class PackingRendererService:
    @staticmethod
    def build_template(
        *,
        packing_list_number: str,
        packing_date: str,
        currency: str,
        customer_name: str,
        customer_code: str,
        country: str,
        consignee: str,
        notify_party: str,
        payment_terms: str,
        delivery_terms: str,
        estimated_delivery: str,
        container_no: str,
        invoice_number: str,
        proforma_number: str,
        seal_no: str,
        port_loading: str,
        port_discharge: str,
        notes: str,
        items: List[PackingItem],
        gross_by_index: dict[int, float],
        selected_pallet: Optional[str] = None,
    ) -> DocumentTemplate:
        lines: List[DocumentLineItem] = []
        total_net = 0.0
        total_gross = 0.0
        for index, item in enumerate(items):
            if selected_pallet and item.pallet_no != selected_pallet:
                continue
            quantity_value = float(item.quantity)
            net_weight = quantity_value * float(item.quantity_weight)
            gross_weight = float(gross_by_index.get(index, 0.0))
            total_net += net_weight
            total_gross += gross_weight

            quantity_text = f"{quantity_value:.3f}".rstrip("0").rstrip(".")
            pieces_text = f"{quantity_text} {str(item.unit or 'PCS').strip()}"
            lines.append(
                DocumentLineItem(
                    line_no=len(lines) + 1,
                    product_code=item.pallet_no,
                    description=item.description if not item.remarks else f"{item.description}\n{item.remarks}",
                    quantity=quantity_text,
                    unit=pieces_text,
                    unit_price=f"{float(item.quantity_weight):.3f} KG",
                    discount="",
                    vat="",
                    total=f"{gross_weight:.3f} KG",
                    amount=f"{net_weight:.3f} KG",
                )
            )

        title = "PACKING LIST" if not selected_pallet else f"PACKING LIST - {selected_pallet}"
        return DocumentTemplate(
            document_title=title,
            filename_base=(packing_list_number or "packing_list").replace("/", "-"),
            document_kind="PACKING_LIST",
            invoice_number=packing_list_number,
            invoice_date=packing_date,
            currency=currency,
            customer_name=customer_name,
            customer_company_name=customer_name,
            customer_country=country,
            customer_code=customer_code,
            bill_to_company=consignee,
            ship_to_company=notify_party,
            payment_terms=payment_terms,
            delivery_terms=delivery_terms,
            estimated_delivery=estimated_delivery,
            packing_type=container_no,
            subtotal=f"{total_net:.3f} KG",
            net_total=f"{total_net:.3f} KG",
            grand_total=f"{total_gross:.3f} KG",
            notes=notes,
            terms_conditions=(
                f"Invoice No: {invoice_number}\n"
                f"Proforma No: {proforma_number}\n"
                f"Container No: {container_no}\n"
                f"Seal No: {seal_no}\n"
                f"Port of Loading: {port_loading}\n"
                f"Port of Discharge: {port_discharge}"
            ),
            items=lines,
        )
