from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from models.base_document_model import BaseDocumentModel
from models.finance_model import FinanceModel


class ProformaModel(BaseDocumentModel):
    db_path = str(Path(__file__).resolve().parent.parent / "database" / "mewa.db")
    table_name = "proforma_headers"
    id_field = "id"
    ALLOWED_STATUSES = {"Draft", "Sent", "Approved", "Rejected", "Converted", "Cancelled"}

    @classmethod
    def _append_history(cls, cursor, proforma_id: int, event_type: str, event_note: str, created_by: str) -> None:
        cursor.execute(
            """
            INSERT INTO proforma_history(proforma_id, event_type, event_note, created_by, created_at)
            VALUES(?,?,?,?,?)
            """,
            (
                int(proforma_id),
                str(event_type or "").strip() or "Unknown",
                str(event_note or "").strip(),
                str(created_by or "SYSTEM"),
                cls.now(),
            ),
        )

    @classmethod
    def conversion_info(cls, invoice_number: str) -> Optional[Dict[str, Any]]:
        detail = cls.invoice_detail(invoice_number)
        if detail is None:
            return None
        converted_to = str(detail.get("converted_invoice_number") or "")
        return {
            "proforma_number": str(detail.get("invoice_number") or ""),
            "status": str(detail.get("status") or "Draft"),
            "converted_invoice_number": converted_to,
            "is_converted": bool(converted_to),
            "can_convert": bool(converted_to == "" and str(detail.get("status") or "").lower() not in ("cancelled", "rejected")),
        }

    @classmethod
    def mark_status(cls, invoice_number: str, status: str, created_by: str = "SYSTEM", note: str = "") -> None:
        target_status = str(status or "").strip().title()
        if target_status not in cls.ALLOWED_STATUSES:
            raise ValueError("Invalid proforma status")

        with cls()._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM proforma_headers WHERE proforma_number = ?", (invoice_number,))
            row = cursor.fetchone()
            if row is None:
                raise ValueError("Proforma not found")
            proforma_id = int(row[0])

            cursor.execute(
                "UPDATE proforma_headers SET status = ?, updated_at = ? WHERE id = ?",
                (target_status, cls.now(), proforma_id),
            )
            cls._append_history(cursor, proforma_id, "StatusChanged", note or f"Status changed to {target_status}", created_by)
            conn.commit()

    @classmethod
    def mark_converted(cls, invoice_number: str, sales_invoice_number: str, created_by: str = "SYSTEM") -> None:
        with cls()._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, COALESCE(converted_invoice_number, '') FROM proforma_headers WHERE proforma_number = ?",
                (invoice_number,),
            )
            row = cursor.fetchone()
            if row is None:
                raise ValueError("Proforma not found")
            proforma_id = int(row[0])
            existing_converted = str(row[1] or "")
            if existing_converted:
                raise ValueError(f"This Proforma has already been converted into Export Sales Invoice {existing_converted}.")

            now_value = cls.now()
            cursor.execute(
                """
                UPDATE proforma_headers
                SET status = 'Converted', converted_invoice_number = ?, converted_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (sales_invoice_number, now_value, now_value, proforma_id),
            )
            cls._append_history(
                cursor,
                proforma_id,
                "Converted",
                f"Converted to Export Sales Invoice {sales_invoice_number}",
                created_by,
            )
            conn.commit()

    @classmethod
    def invoice_number_generate(cls) -> str:
        prefix = datetime.now().strftime("PF-%Y%m%d-")
        with cls()._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT proforma_number
                FROM proforma_headers
                WHERE proforma_number LIKE ?
                ORDER BY proforma_number DESC
                LIMIT 1
                """,
                (f"{prefix}%",),
            )
            row = cursor.fetchone()

        if row is None or not row[0]:
            return f"{prefix}0001"

        try:
            next_no = int(str(row[0]).split("-")[-1]) + 1
        except ValueError:
            next_no = 1
        return f"{prefix}{next_no:04d}"

    @classmethod
    def list_invoices(cls, keyword: str = "") -> List[Dict[str, Any]]:
        params: List[Any] = []
        where_sql = ""
        if keyword and keyword.strip():
            token = f"%{keyword.strip().lower()}%"
            where_sql = """
                WHERE LOWER(ph.proforma_number) LIKE ?
                   OR LOWER(COALESCE(c.firma_unvani, '')) LIKE ?
                   OR LOWER(COALESCE(ph.status, '')) LIKE ?
            """
            params = [token, token, token]

        with cls()._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"""
                SELECT
                    ph.id,
                    ph.proforma_number AS invoice_number,
                    ph.issue_date AS invoice_date,
                    ph.expiry_date AS due_date,
                    COALESCE(c.firma_unvani, '') AS customer_name,
                    COALESCE(c.cari_kodu, '') AS customer_code,
                    COALESCE(ph.currency, 'USD') AS currency,
                    COALESCE(ph.exchange_rate, 1) AS exchange_rate,
                    COALESCE(ph.subtotal, 0) AS subtotal,
                    COALESCE(ph.discount_total, 0) AS discount_total,
                    COALESCE(ph.vat_total, 0) AS vat_total,
                    COALESCE(ph.grand_total, 0) AS grand_total,
                    COALESCE(ph.status, 'Draft') AS status,
                    COALESCE(ph.created_by, 'SYSTEM') AS created_by,
                    COALESCE(ph.converted_invoice_number, '') AS converted_invoice_number,
                    ph.customer_id,
                    COALESCE(ph.notes, '') AS notes
                FROM proforma_headers ph
                LEFT JOIN cariler c ON c.id = ph.customer_id
                {where_sql}
                ORDER BY ph.issue_date DESC, ph.id DESC
                """,
                params,
            )
            return cls.rows_to_dicts(cursor, cursor.fetchall())

    @classmethod
    def invoice_detail(cls, invoice_number: str) -> Optional[Dict[str, Any]]:
        with cls()._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT
                    ph.id,
                    ph.proforma_number AS invoice_number,
                    ph.customer_id,
                    COALESCE(c.firma_unvani, '') AS customer_name,
                    COALESCE(c.cari_kodu, '') AS customer_code,
                    ph.issue_date AS invoice_date,
                    ph.expiry_date AS due_date,
                    COALESCE(ph.currency, 'USD') AS currency,
                    COALESCE(ph.exchange_rate, 1) AS exchange_rate,
                    COALESCE(ph.subtotal, 0) AS subtotal,
                    COALESCE(ph.discount_total, 0) AS discount_total,
                    COALESCE(ph.vat_total, 0) AS vat_total,
                    COALESCE(ph.grand_total, 0) AS grand_total,
                    COALESCE(ph.status, 'Draft') AS status,
                    COALESCE(ph.notes, '') AS notes,
                    COALESCE(ph.payment_terms, '') AS payment_terms,
                    COALESCE(ph.delivery_terms, '') AS delivery_terms,
                    COALESCE(ph.converted_invoice_number, '') AS converted_invoice_number,
                    COALESCE(ph.created_by, 'SYSTEM') AS created_by
                FROM proforma_headers ph
                LEFT JOIN cariler c ON c.id = ph.customer_id
                WHERE ph.proforma_number = ?
                """,
                (invoice_number,),
            )
            headers = cls.rows_to_dicts(cursor, cursor.fetchall())
            if not headers:
                return None

            header = headers[0]
            cursor.execute(
                """
                SELECT
                    pl.id,
                    pl.stock_id,
                    COALESCE(st.stock_code, '') AS stock_code,
                    COALESCE(st.product_name, '') AS product_name,
                    COALESCE(st.hs_code, '') AS hs_code,
                    COALESCE(st.weight, 0) AS weight,
                    COALESCE(pl.quantity, 0) AS quantity,
                    COALESCE(pl.unit, '') AS unit,
                    COALESCE(pl.unit_price, 0) AS unit_price,
                    COALESCE(pl.discount_percent, 0) AS discount_percent,
                    COALESCE(pl.vat_percent, 0) AS vat_percent,
                    COALESCE(pl.line_total, 0) AS line_total
                FROM proforma_lines pl
                LEFT JOIN stoklar st ON st.id = pl.stock_id
                WHERE pl.proforma_id = ?
                ORDER BY pl.id
                """,
                (int(header["id"]),),
            )
            header["items"] = cls.rows_to_dicts(cursor, cursor.fetchall())
            return header

    @classmethod
    def save_invoice(
        cls,
        invoice_number: str,
        customer_id: int,
        invoice_date: str,
        due_date: str,
        currency: str,
        exchange_rate: float,
        notes: str,
        payment_terms: str,
        delivery_terms: str,
        items: List[Dict[str, Any]],
        created_by: str = "SYSTEM",
        existing_invoice_number: Optional[str] = None,
        status: str = "Draft",
    ) -> int:
        now_value = cls.now()
        status_value = str(status or "Draft").strip().title()
        if status_value not in cls.ALLOWED_STATUSES:
            status_value = "Draft"

        with cls()._connect() as conn:
            cursor = conn.cursor()
            if existing_invoice_number:
                cursor.execute(
                    "SELECT id FROM proforma_headers WHERE proforma_number = ? AND proforma_number != ?",
                    (invoice_number, existing_invoice_number),
                )
            else:
                cursor.execute("SELECT id FROM proforma_headers WHERE proforma_number = ?", (invoice_number,))
            if cursor.fetchone() is not None:
                raise ValueError("Proforma number already exists")

        subtotal = 0.0
        discount_total = 0.0
        vat_total = 0.0
        clean_items: List[Dict[str, Any]] = []

        for item in items:
            qty = float(item.get("quantity") or 0)
            if qty <= 0:
                continue
            unit_price = float(item.get("unit_price") or 0)
            discount_percent = float(item.get("discount_percent") or 0)
            vat_percent = float(item.get("vat_percent") or 0)

            base = qty * unit_price
            discount_amount = base * (discount_percent / 100.0)
            net = base - discount_amount
            vat_amount = net * (vat_percent / 100.0)
            line_total = net + vat_amount

            subtotal += base
            discount_total += discount_amount
            vat_total += vat_amount

            payload = dict(item)
            payload["line_total"] = line_total
            clean_items.append(payload)

        if not clean_items:
            raise ValueError("At least one proforma item with quantity > 0 is required")

        grand_total = subtotal - discount_total + vat_total

        with cls()._connect() as conn:
            cursor = conn.cursor()

            if existing_invoice_number:
                cursor.execute(
                    "SELECT id FROM proforma_headers WHERE proforma_number = ?",
                    (existing_invoice_number,),
                )
                row = cursor.fetchone()
                if row is None:
                    raise ValueError("Proforma not found")
                invoice_id = int(row[0])

                cursor.execute(
                    """
                    UPDATE proforma_headers
                    SET
                        proforma_number = ?,
                        customer_id = ?,
                        issue_date = ?,
                        expiry_date = ?,
                        currency = ?,
                        exchange_rate = ?,
                        subtotal = ?,
                        discount_total = ?,
                        vat_total = ?,
                        grand_total = ?,
                        payment_terms = ?,
                        delivery_terms = ?,
                        notes = ?,
                        status = ?,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        invoice_number,
                        customer_id,
                        invoice_date,
                        due_date or None,
                        currency or "USD",
                        exchange_rate,
                        subtotal,
                        discount_total,
                        vat_total,
                        grand_total,
                        payment_terms,
                        delivery_terms,
                        notes,
                        status_value,
                        now_value,
                        invoice_id,
                    ),
                )
                cursor.execute("DELETE FROM proforma_lines WHERE proforma_id = ?", (invoice_id,))
                cls._append_history(cursor, invoice_id, "Updated", "Proforma updated", created_by)
            else:
                cursor.execute(
                    """
                    INSERT INTO proforma_headers(
                        proforma_number,
                        customer_id,
                        issue_date,
                        expiry_date,
                        currency,
                        exchange_rate,
                        subtotal,
                        discount_total,
                        vat_total,
                        grand_total,
                        status,
                        payment_terms,
                        delivery_terms,
                        notes,
                        created_by,
                        created_at,
                        updated_at
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        invoice_number,
                        customer_id,
                        invoice_date,
                        due_date or None,
                        currency or "USD",
                        exchange_rate,
                        subtotal,
                        discount_total,
                        vat_total,
                        grand_total,
                        status_value,
                        payment_terms,
                        delivery_terms,
                        notes,
                        created_by or "SYSTEM",
                        now_value,
                        now_value,
                    ),
                )
                invoice_id = int(cursor.lastrowid)
                cls._append_history(cursor, invoice_id, "Created", "Proforma created", created_by)

            for item in clean_items:
                cursor.execute(
                    """
                    INSERT INTO proforma_lines(
                        proforma_id,
                        stock_id,
                        quantity,
                        unit,
                        unit_price,
                        discount_percent,
                        vat_percent,
                        line_total,
                        created_at
                    ) VALUES(?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        invoice_id,
                        int(item.get("stock_id") or 0),
                        float(item.get("quantity") or 0),
                        str(item.get("unit") or ""),
                        float(item.get("unit_price") or 0),
                        float(item.get("discount_percent") or 0),
                        float(item.get("vat_percent") or 0),
                        float(item.get("line_total") or 0),
                        now_value,
                    ),
                )

            conn.commit()

        return invoice_id

    @classmethod
    def cancel_invoice(cls, invoice_number: str) -> None:
        with cls()._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM proforma_headers WHERE proforma_number = ?", (invoice_number,))
            row = cursor.fetchone()
            if row is None:
                return
            proforma_id = int(row[0])
            cursor.execute(
                "UPDATE proforma_headers SET status = ?, updated_at = ? WHERE proforma_number = ?",
                ("Cancelled", cls.now(), invoice_number),
            )
            cls._append_history(cursor, proforma_id, "StatusChanged", "Status changed to Cancelled", "SYSTEM")
            conn.commit()

    @classmethod
    def delete_invoice(cls, invoice_number: str, *, is_admin: bool = False) -> None:
        number = str(invoice_number or "").strip()
        if not number:
            raise ValueError("Proforma numarası gereklidir.")

        with cls()._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, COALESCE(status, 'Draft') FROM proforma_headers WHERE proforma_number = ?",
                (number,),
            )
            row = cursor.fetchone()
            if row is None:
                raise ValueError("Proforma bulunamadı.")

            proforma_id = int(row[0])
            status = str(row[1] or "Draft").strip().lower()
            if status not in {"draft", "cancelled"} and not is_admin:
                raise ValueError("İşlenmiş belge doğrudan silinemez. Önce iptal edin.")

            cursor.execute("BEGIN TRANSACTION")
            try:
                cursor.execute("DELETE FROM proforma_lines WHERE proforma_id = ?", (proforma_id,))
                cursor.execute("DELETE FROM proforma_history WHERE proforma_id = ?", (proforma_id,))
                cursor.execute("DELETE FROM proforma_headers WHERE id = ?", (proforma_id,))
                conn.commit()
            except Exception:
                conn.rollback()
                raise

        FinanceModel.notify_change("proforma")
