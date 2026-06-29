from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.crud_base import BaseCrud


class ExportSalesInvoiceModel(BaseCrud):
    db_path = str(Path(__file__).resolve().parent.parent / "database" / "mewa.db")
    table_name = "sales_invoices"
    id_field = "id"

    @staticmethod
    def _now() -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def _rows_to_dicts(cursor, rows) -> List[Dict[str, Any]]:
        columns = [column[0] for column in cursor.description] if cursor.description else []
        return [dict(zip(columns, row)) for row in rows]

    @classmethod
    def invoice_number_generate(cls) -> str:
        prefix = datetime.now().strftime("SI-%Y%m%d-")
        with cls()._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT invoice_number
                FROM sales_invoices
                WHERE invoice_number LIKE ?
                ORDER BY invoice_number DESC
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
    def _table_has_column(cls, cursor, table_name: str, column_name: str) -> bool:
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = {str(row[1]).lower() for row in cursor.fetchall()}
        return column_name.lower() in columns

    @classmethod
    def resolve_or_create_customer_id(
        cls,
        customer_id: int,
        cari_kodu: str,
        firma_unvani: str,
        default_currency: str = "USD",
    ) -> int:
        if customer_id > 0:
            return customer_id

        code = str(cari_kodu or "").strip()
        company = str(firma_unvani or "").strip()
        if not company:
            return 0

        with cls()._connect() as conn:
            cursor = conn.cursor()

            if code:
                cursor.execute(
                    "SELECT id FROM cariler WHERE LOWER(COALESCE(cari_kodu, '')) = LOWER(?)",
                    (code,),
                )
                row = cursor.fetchone()
                if row is not None:
                    return int(row[0])

            cursor.execute(
                "SELECT id FROM cariler WHERE LOWER(COALESCE(firma_unvani, '')) = LOWER(?)",
                (company,),
            )
            row = cursor.fetchone()
            if row is not None:
                return int(row[0])

            generated_code = code or f"CR-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            cursor.execute(
                "SELECT 1 FROM cariler WHERE LOWER(cari_kodu) = LOWER(?)",
                (generated_code,),
            )
            if cursor.fetchone() is not None:
                generated_code = f"{generated_code}-{datetime.now().strftime('%f')[:4]}"

            columns = {
                "cari_kodu": generated_code,
                "firma_unvani": company,
                "yetkili": company,
                "telefon": "",
                "email": "-",
                "vergi_dairesi": "-",
                "vergi_no": "-",
                "ulke": "-",
                "sehir": "-",
                "ilce": "-",
                "adres": "-",
            }

            if cls._table_has_column(cursor, "cariler", "default_currency"):
                columns["default_currency"] = str(default_currency or "USD").strip() or "USD"
            if cls._table_has_column(cursor, "cariler", "cari_tipi"):
                columns["cari_tipi"] = "Müşteri"

            field_names = ", ".join(columns.keys())
            placeholders = ", ".join(["?"] * len(columns))
            cursor.execute(
                f"INSERT INTO cariler({field_names}) VALUES({placeholders})",
                tuple(columns.values()),
            )
            conn.commit()
            return int(cursor.lastrowid)

    @classmethod
    def _resolve_or_create_supplier_bridge(
        cls,
        cursor,
        cari_kodu: str,
        company_name: str,
        default_currency: str = "USD",
    ) -> int:
        code = str(cari_kodu or "").strip()
        company = str(company_name or "").strip()

        if code:
            cursor.execute(
                "SELECT id FROM suppliers WHERE LOWER(COALESCE(supplier_code, '')) = LOWER(?)",
                (code,),
            )
            row = cursor.fetchone()
            if row is not None:
                return int(row[0])

        cursor.execute(
            "SELECT id FROM suppliers WHERE LOWER(COALESCE(company_name, '')) = LOWER(?)",
            (company,),
        )
        row = cursor.fetchone()
        if row is not None:
            return int(row[0])

        supplier_code = code or f"CR-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        cursor.execute(
            "SELECT 1 FROM suppliers WHERE LOWER(supplier_code) = LOWER(?)",
            (supplier_code,),
        )
        if cursor.fetchone() is not None:
            supplier_code = f"{supplier_code}-{datetime.now().strftime('%f')[:4]}"

        cursor.execute(
            """
            INSERT INTO suppliers(
                supplier_code,
                company_name,
                contact_person,
                default_currency,
                payment_term
            ) VALUES(?,?,?,?,?)
            """,
            (
                supplier_code,
                company,
                company,
                str(default_currency or "USD").strip() or "USD",
                "",
            ),
        )
        return int(cursor.lastrowid)

    @classmethod
    def list_invoices(cls, keyword: str = "") -> List[Dict[str, Any]]:
        params: List[Any] = []
        where_sql = ""
        if keyword and keyword.strip():
            token = f"%{keyword.strip().lower()}%"
            where_sql = """
                WHERE LOWER(si.invoice_number) LIKE ?
                   OR LOWER(COALESCE(c.firma_unvani, '')) LIKE ?
                   OR LOWER(COALESCE(si.status, '')) LIKE ?
            """
            params = [token, token, token]

        with cls()._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"""
                SELECT
                    si.id,
                    si.invoice_number,
                    si.invoice_date,
                    si.due_date,
                    COALESCE(c.firma_unvani, '') AS customer_name,
                    COALESCE(c.cari_kodu, '') AS customer_code,
                    COALESCE(si.currency, 'USD') AS currency,
                    COALESCE(si.exchange_rate, 1) AS exchange_rate,
                    COALESCE(si.subtotal, 0) AS subtotal,
                    COALESCE(si.discount_total, 0) AS discount_total,
                    COALESCE(si.vat_total, 0) AS vat_total,
                    COALESCE(si.grand_total, 0) AS grand_total,
                    COALESCE(si.status, 'Posted') AS status,
                    COALESCE(si.created_by, 'SYSTEM') AS created_by,
                    COALESCE(si.source_proforma_number, '') AS source_proforma_number,
                    COALESCE(si.payment_terms, '') AS payment_terms,
                    COALESCE(si.delivery_terms, '') AS delivery_terms,
                    si.customer_id,
                    si.notes
                FROM sales_invoices si
                LEFT JOIN cariler c ON c.id = si.customer_id
                {where_sql}
                ORDER BY si.invoice_date DESC, si.id DESC
                """,
                params,
            )
            return cls._rows_to_dicts(cursor, cursor.fetchall())

    @classmethod
    def invoice_detail(cls, invoice_number: str) -> Optional[Dict[str, Any]]:
        with cls()._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT
                    si.id,
                    si.invoice_number,
                    si.customer_id,
                    COALESCE(c.firma_unvani, '') AS customer_name,
                    COALESCE(c.cari_kodu, '') AS customer_code,
                    si.invoice_date,
                    si.due_date,
                    COALESCE(si.currency, 'USD') AS currency,
                    COALESCE(si.exchange_rate, 1) AS exchange_rate,
                    COALESCE(si.subtotal, 0) AS subtotal,
                    COALESCE(si.discount_total, 0) AS discount_total,
                    COALESCE(si.vat_total, 0) AS vat_total,
                    COALESCE(si.grand_total, 0) AS grand_total,
                    COALESCE(si.status, 'Posted') AS status,
                    COALESCE(si.notes, '') AS notes,
                    COALESCE(si.source_proforma_number, '') AS source_proforma_number,
                    COALESCE(si.payment_terms, '') AS payment_terms,
                    COALESCE(si.delivery_terms, '') AS delivery_terms,
                    COALESCE(si.created_by, 'SYSTEM') AS created_by
                FROM sales_invoices si
                LEFT JOIN cariler c ON c.id = si.customer_id
                WHERE si.invoice_number = ?
                """,
                (invoice_number,),
            )
            headers = cls._rows_to_dicts(cursor, cursor.fetchall())
            if not headers:
                return None

            header = headers[0]
            cursor.execute(
                """
                SELECT
                    sii.id,
                    sii.stock_id,
                    COALESCE(st.stock_code, '') AS stock_code,
                    COALESCE(st.product_name, '') AS product_name,
                    COALESCE(st.hs_code, '') AS hs_code,
                    COALESCE(st.weight, 0) AS weight,
                    COALESCE(sii.quantity, 0) AS quantity,
                    COALESCE(sii.unit, '') AS unit,
                    COALESCE(sii.unit_price, 0) AS unit_price,
                    COALESCE(sii.discount_percent, 0) AS discount_percent,
                    COALESCE(sii.vat_percent, 0) AS vat_percent,
                    COALESCE(sii.line_total, 0) AS line_total
                FROM sales_invoice_items sii
                LEFT JOIN stoklar st ON st.id = sii.stock_id
                WHERE sii.invoice_id = ?
                ORDER BY sii.id
                """,
                (int(header["id"]),),
            )
            header["items"] = cls._rows_to_dicts(cursor, cursor.fetchall())
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
        items: List[Dict[str, Any]],
        created_by: str = "SYSTEM",
        existing_invoice_number: Optional[str] = None,
        source_proforma_number: str = "",
        payment_terms: str = "",
        delivery_terms: str = "",
    ) -> int:
        now_value = cls._now()

        with cls()._connect() as conn:
            cursor = conn.cursor()
            if existing_invoice_number:
                cursor.execute(
                    "SELECT id FROM sales_invoices WHERE invoice_number = ? AND invoice_number != ?",
                    (invoice_number, existing_invoice_number),
                )
            else:
                cursor.execute("SELECT id FROM sales_invoices WHERE invoice_number = ?", (invoice_number,))
            duplicate_row = cursor.fetchone()
            if duplicate_row is not None:
                raise ValueError("Invoice number already exists")

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
            raise ValueError("At least one invoice item with quantity > 0 is required")

        grand_total = subtotal - discount_total + vat_total

        with cls()._connect() as conn:
            cursor = conn.cursor()

            if existing_invoice_number:
                cursor.execute("SELECT id FROM sales_invoices WHERE invoice_number = ?", (existing_invoice_number,))
                row = cursor.fetchone()
                if row is None:
                    raise ValueError("Sales invoice not found")
                invoice_id = int(row[0])

                cursor.execute(
                    """
                    SELECT stock_id, COALESCE(quantity, 0)
                    FROM sales_invoice_items
                    WHERE invoice_id = ?
                    """,
                    (invoice_id,),
                )
                old_items = cursor.fetchall()
                for old_stock_id, old_qty in old_items:
                    sid = int(old_stock_id or 0)
                    qty = float(old_qty or 0)
                    if sid > 0 and qty > 0:
                        cursor.execute(
                            "UPDATE stoklar SET current_stock = COALESCE(current_stock, 0) + ? WHERE id = ?",
                            (qty, sid),
                        )

                cursor.execute(
                    "DELETE FROM stock_movements WHERE reference_type = ? AND reference_no = ?",
                    ("SalesInvoice", existing_invoice_number),
                )
                cursor.execute(
                    "DELETE FROM customer_account_movements WHERE reference_type = ? AND reference_no = ?",
                    ("SalesInvoice", existing_invoice_number),
                )
                cursor.execute(
                    "DELETE FROM supplier_account_movements WHERE reference_type = ? AND reference_no = ?",
                    ("SalesInvoice", existing_invoice_number),
                )

                cursor.execute(
                    """
                    UPDATE sales_invoices
                    SET
                        invoice_number = ?,
                        customer_id = ?,
                        invoice_date = ?,
                        due_date = ?,
                        currency = ?,
                        exchange_rate = ?,
                        subtotal = ?,
                        discount_total = ?,
                        vat_total = ?,
                        grand_total = ?,
                        source_proforma_number = ?,
                        payment_terms = ?,
                        delivery_terms = ?,
                        notes = ?,
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
                        source_proforma_number,
                        payment_terms,
                        delivery_terms,
                        notes,
                        now_value,
                        invoice_id,
                    ),
                )

                cursor.execute("DELETE FROM sales_invoice_items WHERE invoice_id = ?", (invoice_id,))
            else:
                cursor.execute(
                    """
                    INSERT INTO sales_invoices(
                        invoice_number,
                        customer_id,
                        invoice_date,
                        due_date,
                        currency,
                        exchange_rate,
                        subtotal,
                        discount_total,
                        vat_total,
                        grand_total,
                        status,
                        source_proforma_number,
                        payment_terms,
                        delivery_terms,
                        notes,
                        created_by,
                        created_at,
                        updated_at
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
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
                        "Posted",
                        source_proforma_number,
                        payment_terms,
                        delivery_terms,
                        notes,
                        created_by or "SYSTEM",
                        now_value,
                        now_value,
                    ),
                )
                invoice_id = int(cursor.lastrowid)

            for item in clean_items:
                stock_id = int(item.get("stock_id") or 0)
                quantity = float(item.get("quantity") or 0)

                cursor.execute(
                    """
                    INSERT INTO sales_invoice_items(
                        invoice_id,
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
                        stock_id,
                        quantity,
                        str(item.get("unit") or ""),
                        float(item.get("unit_price") or 0),
                        float(item.get("discount_percent") or 0),
                        float(item.get("vat_percent") or 0),
                        float(item.get("line_total") or 0),
                        now_value,
                    ),
                )
                invoice_line_id = int(cursor.lastrowid or 0)

                if stock_id > 0 and quantity > 0:
                    cursor.execute(
                        "UPDATE stoklar SET current_stock = COALESCE(current_stock, 0) - ? WHERE id = ?",
                        (quantity, stock_id),
                    )
                    cursor.execute(
                        """
                        INSERT INTO stock_movements(
                            stock_id,
                            movement_type,
                            quantity,
                            reference_type,
                            reference_no,
                            movement_date,
                            warehouse,
                            notes,
                            created_at
                        ) VALUES(?,?,?,?,?,?,?,?,?)
                        """,
                        (
                            stock_id,
                            "SALE",
                            quantity,
                            "SalesInvoice",
                            invoice_number,
                            invoice_date,
                            "",
                            f"Sales Invoice {invoice_number} Line {invoice_line_id}",
                            now_value,
                        ),
                    )

            cursor.execute(
                """
                SELECT
                    COALESCE(cari_kodu, '') AS cari_kodu,
                    COALESCE(firma_unvani, '') AS firma_unvani
                FROM cariler
                WHERE id = ?
                """,
                (customer_id,),
            )
            customer = cursor.fetchone() or ("", "")
            customer_code = str(customer[0] or "")
            customer_name = str(customer[1] or "")

            cursor.execute(
                """
                INSERT INTO customer_account_movements(
                    customer_id,
                    movement_date,
                    movement_type,
                    reference_type,
                    reference_no,
                    amount,
                    currency,
                    exchange_rate,
                    description,
                    status,
                    created_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    customer_id,
                    invoice_date,
                    "Credit",
                    "SalesInvoice",
                    invoice_number,
                    grand_total,
                    currency or "USD",
                    exchange_rate,
                    f"Invoice No: {invoice_number}",
                    "Posted",
                    now_value,
                ),
            )

            # Bridge write for existing customer ledger screen that reads supplier_account_movements.
            bridge_supplier_id = cls._resolve_or_create_supplier_bridge(
                cursor,
                customer_code,
                customer_name,
                currency,
            )
            cursor.execute(
                """
                INSERT INTO supplier_account_movements(
                    supplier_id,
                    movement_date,
                    movement_type,
                    reference_type,
                    reference_no,
                    amount,
                    currency,
                    exchange_rate,
                    description,
                    status,
                    created_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    bridge_supplier_id,
                    invoice_date,
                    "Credit",
                    "SalesInvoice",
                    invoice_number,
                    grand_total,
                    currency or "USD",
                    exchange_rate,
                    f"Invoice No: {invoice_number}",
                    "Posted",
                    now_value,
                ),
            )

            conn.commit()

        return invoice_id

    @classmethod
    def cancel_invoice(cls, invoice_number: str) -> None:
        with cls()._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id FROM sales_invoices WHERE invoice_number = ?",
                (invoice_number,),
            )
            row = cursor.fetchone()
            if row is None:
                return
            invoice_id = int(row[0])

            cursor.execute(
                """
                SELECT stock_id, COALESCE(quantity, 0)
                FROM sales_invoice_items
                WHERE invoice_id = ?
                """,
                (invoice_id,),
            )
            stock_rows = cursor.fetchall()
            for stock_id, qty in stock_rows:
                sid = int(stock_id or 0)
                amount = float(qty or 0)
                if sid > 0 and amount > 0:
                    cursor.execute(
                        "UPDATE stoklar SET current_stock = COALESCE(current_stock, 0) + ? WHERE id = ?",
                        (amount, sid),
                    )

            cursor.execute(
                "UPDATE sales_invoices SET status = ?, updated_at = ? WHERE invoice_number = ?",
                ("Cancelled", cls._now(), invoice_number),
            )
            cursor.execute(
                """
                UPDATE customer_account_movements
                SET status = ?
                WHERE reference_type = ? AND reference_no = ?
                """,
                ("Cancelled", "SalesInvoice", invoice_number),
            )
            cursor.execute(
                """
                UPDATE supplier_account_movements
                SET status = ?
                WHERE reference_type = ? AND reference_no = ?
                """,
                ("Cancelled", "SalesInvoice", invoice_number),
            )
            cursor.execute(
                "DELETE FROM stock_movements WHERE reference_type = ? AND reference_no = ?",
                ("SalesInvoice", invoice_number),
            )
            conn.commit()
