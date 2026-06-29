from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.crud_base import BaseCrud


class PurchaseInvoiceModel(BaseCrud):
    db_path = str(Path(__file__).resolve().parent.parent / "database" / "mewa.db")
    table_name = "purchase_invoices"
    id_field = "id"

    @staticmethod
    def _now() -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def _rows_to_dicts(cursor, rows) -> List[Dict[str, Any]]:
        columns = [column[0] for column in cursor.description] if cursor.description else []
        return [dict(zip(columns, row)) for row in rows]

    @classmethod
    def resolve_or_create_supplier_id(
        cls,
        supplier_id: int,
        cari_kodu: str,
        firma_unvani: str,
        default_currency: str = "USD",
        payment_term: str = "",
        yetkili: str = "",
    ) -> int:
        if supplier_id > 0:
            return supplier_id

        code = str(cari_kodu or "").strip()
        company = str(firma_unvani or "").strip()
        if not company:
            return 0

        with cls()._connect() as conn:
            cursor = conn.cursor()

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
                    str(yetkili or company).strip() or company,
                    str(default_currency or "USD").strip() or "USD",
                    str(payment_term or "").strip(),
                ),
            )
            conn.commit()
            return int(cursor.lastrowid)

    @classmethod
    def invoice_number_generate(cls) -> str:
        prefix = datetime.now().strftime("PI-%Y%m%d-")
        with cls()._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT invoice_number
                FROM purchase_invoices
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
    def goods_receipts_lookup(cls) -> List[Dict[str, Any]]:
        with cls()._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT
                    gr.id,
                    gr.receipt_number,
                    gr.purchase_order_id,
                    COALESCE(po.order_number, '') AS purchase_order_number,
                    gr.supplier_id,
                    COALESCE(s.company_name, '') AS supplier_name,
                    COALESCE(po.currency, 'USD') AS currency,
                    COALESCE(po.exchange_rate, 1) AS exchange_rate,
                    gr.receipt_date,
                    COALESCE(gr.status, 'Posted') AS status
                FROM goods_receipts gr
                LEFT JOIN purchase_orders po ON po.id = gr.purchase_order_id
                LEFT JOIN suppliers s ON s.id = gr.supplier_id
                WHERE LOWER(COALESCE(gr.status, '')) != 'cancelled'
                ORDER BY gr.receipt_date DESC, gr.id DESC
                """
            )
            return cls._rows_to_dicts(cursor, cursor.fetchall())

    @classmethod
    def goods_receipt_items_for_invoice(cls, goods_receipt_id: int) -> List[Dict[str, Any]]:
        with cls()._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT
                    gri.id AS goods_receipt_item_id,
                    gri.stock_id,
                    COALESCE(st.stock_code, '') AS stock_code,
                    COALESCE(st.product_name, '') AS product_name,
                    COALESCE(gri.received_qty, 0) AS received_qty,
                    COALESCE(gri.unit, '') AS unit,
                    COALESCE(poi.unit_price, 0) AS unit_price,
                    COALESCE(poi.discount_percent, 0) AS discount_percent,
                    COALESCE(poi.vat_percent, 0) AS vat_percent,
                    COALESCE(SUM(
                        CASE
                            WHEN LOWER(COALESCE(pi.status, '')) = 'cancelled' THEN 0
                            ELSE pii.quantity
                        END
                    ), 0) AS invoiced_qty
                FROM goods_receipt_items gri
                LEFT JOIN stoklar st ON st.id = gri.stock_id
                LEFT JOIN purchase_order_items poi ON poi.id = gri.purchase_order_item_id
                LEFT JOIN purchase_invoice_items pii ON pii.goods_receipt_item_id = gri.id
                LEFT JOIN purchase_invoices pi ON pi.id = pii.invoice_id
                WHERE gri.receipt_id = ?
                GROUP BY gri.id
                ORDER BY gri.id
                """,
                (goods_receipt_id,),
            )
            rows = cls._rows_to_dicts(cursor, cursor.fetchall())

        for row in rows:
            received_qty = float(row.get("received_qty") or 0)
            invoiced_qty = float(row.get("invoiced_qty") or 0)
            row["remaining_qty"] = max(received_qty - invoiced_qty, 0)
        return rows

    @classmethod
    def list_invoices(cls, keyword: str = "") -> List[Dict[str, Any]]:
        params: List[Any] = []
        where_sql = ""
        if keyword and keyword.strip():
            token = f"%{keyword.strip().lower()}%"
            where_sql = """
                WHERE LOWER(pi.invoice_number) LIKE ?
                   OR LOWER(COALESCE(s.company_name, '')) LIKE ?
                   OR LOWER(COALESCE(po.order_number, '')) LIKE ?
                   OR LOWER(COALESCE(gr.receipt_number, '')) LIKE ?
                   OR LOWER(COALESCE(pi.status, '')) LIKE ?
            """
            params = [token, token, token, token, token]

        with cls()._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"""
                SELECT
                    pi.id,
                    pi.invoice_number,
                    pi.invoice_date,
                    pi.due_date,
                    COALESCE(s.company_name, '') AS supplier_name,
                    COALESCE(po.order_number, '') AS purchase_order_number,
                    COALESCE(gr.receipt_number, '') AS goods_receipt_number,
                    COALESCE(pi.currency, 'USD') AS currency,
                    COALESCE(pi.exchange_rate, 1) AS exchange_rate,
                    COALESCE(pi.subtotal, 0) AS subtotal,
                    COALESCE(pi.discount_total, 0) AS discount_total,
                    COALESCE(pi.vat_total, 0) AS vat_total,
                    COALESCE(pi.grand_total, 0) AS grand_total,
                    COALESCE(pi.status, 'Posted') AS status,
                    COALESCE(pi.created_by, 'SYSTEM') AS created_by,
                    pi.supplier_id,
                    pi.purchase_order_id,
                    pi.goods_receipt_id,
                    pi.notes
                FROM purchase_invoices pi
                LEFT JOIN suppliers s ON s.id = pi.supplier_id
                LEFT JOIN purchase_orders po ON po.id = pi.purchase_order_id
                LEFT JOIN goods_receipts gr ON gr.id = pi.goods_receipt_id
                {where_sql}
                ORDER BY pi.invoice_date DESC, pi.id DESC
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
                    pi.id,
                    pi.invoice_number,
                    pi.supplier_id,
                    COALESCE(s.company_name, '') AS supplier_name,
                    pi.purchase_order_id,
                    COALESCE(po.order_number, '') AS purchase_order_number,
                    pi.goods_receipt_id,
                    COALESCE(gr.receipt_number, '') AS goods_receipt_number,
                    pi.invoice_date,
                    pi.due_date,
                    COALESCE(pi.currency, 'USD') AS currency,
                    COALESCE(pi.exchange_rate, 1) AS exchange_rate,
                    COALESCE(pi.subtotal, 0) AS subtotal,
                    COALESCE(pi.discount_total, 0) AS discount_total,
                    COALESCE(pi.vat_total, 0) AS vat_total,
                    COALESCE(pi.grand_total, 0) AS grand_total,
                    COALESCE(pi.status, 'Posted') AS status,
                    COALESCE(pi.notes, '') AS notes,
                    COALESCE(pi.created_by, 'SYSTEM') AS created_by
                FROM purchase_invoices pi
                LEFT JOIN suppliers s ON s.id = pi.supplier_id
                LEFT JOIN purchase_orders po ON po.id = pi.purchase_order_id
                LEFT JOIN goods_receipts gr ON gr.id = pi.goods_receipt_id
                WHERE pi.invoice_number = ?
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
                    pii.id,
                    pii.goods_receipt_item_id,
                    pii.stock_id,
                    COALESCE(st.stock_code, '') AS stock_code,
                    COALESCE(st.product_name, '') AS product_name,
                    COALESCE(pii.quantity, 0) AS quantity,
                    COALESCE(pii.unit, '') AS unit,
                    COALESCE(pii.unit_price, 0) AS unit_price,
                    COALESCE(pii.discount_percent, 0) AS discount_percent,
                    COALESCE(pii.vat_percent, 0) AS vat_percent,
                    COALESCE(pii.line_total, 0) AS line_total
                FROM purchase_invoice_items pii
                LEFT JOIN stoklar st ON st.id = pii.stock_id
                WHERE pii.invoice_id = ?
                ORDER BY pii.id
                """,
                (int(header["id"]),),
            )
            header["items"] = cls._rows_to_dicts(cursor, cursor.fetchall())
            return header

    @classmethod
    def save_invoice(
        cls,
        invoice_number: str,
        supplier_id: int,
        purchase_order_id: int,
        goods_receipt_id: int,
        invoice_date: str,
        due_date: str,
        currency: str,
        exchange_rate: float,
        notes: str,
        items: List[Dict[str, Any]],
        created_by: str = "SYSTEM",
        existing_invoice_number: Optional[str] = None,
    ) -> int:
        now_value = cls._now()

        with cls()._connect() as conn:
            cursor = conn.cursor()
            if existing_invoice_number:
                cursor.execute(
                    "SELECT id FROM purchase_invoices WHERE invoice_number = ? AND invoice_number != ?",
                    (invoice_number, existing_invoice_number),
                )
            else:
                cursor.execute("SELECT id FROM purchase_invoices WHERE invoice_number = ?", (invoice_number,))
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
                cursor.execute("SELECT id FROM purchase_invoices WHERE invoice_number = ?", (existing_invoice_number,))
                row = cursor.fetchone()
                if row is None:
                    raise ValueError("Purchase invoice not found")
                invoice_id = int(row[0])

                # Roll back old stock effect and old stock movement logs before rewriting invoice.
                cursor.execute(
                    """
                    SELECT stock_id, COALESCE(quantity, 0)
                    FROM purchase_invoice_items
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
                            "UPDATE stoklar SET current_stock = COALESCE(current_stock, 0) - ? WHERE id = ?",
                            (qty, sid),
                        )

                cursor.execute(
                    "DELETE FROM stock_movements WHERE reference_type = ? AND reference_no = ?",
                    ("PurchaseInvoice", existing_invoice_number),
                )

                cursor.execute(
                    """
                    UPDATE purchase_invoices
                    SET
                        invoice_number = ?,
                        supplier_id = ?,
                        purchase_order_id = ?,
                        goods_receipt_id = ?,
                        invoice_date = ?,
                        due_date = ?,
                        currency = ?,
                        exchange_rate = ?,
                        subtotal = ?,
                        discount_total = ?,
                        vat_total = ?,
                        grand_total = ?,
                        notes = ?,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        invoice_number,
                        supplier_id,
                        purchase_order_id or None,
                        goods_receipt_id,
                        invoice_date,
                        due_date or None,
                        currency or "USD",
                        exchange_rate,
                        subtotal,
                        discount_total,
                        vat_total,
                        grand_total,
                        notes,
                        now_value,
                        invoice_id,
                    ),
                )

                cursor.execute("DELETE FROM purchase_invoice_items WHERE invoice_id = ?", (invoice_id,))
                cursor.execute(
                    "DELETE FROM supplier_account_movements WHERE reference_type = ? AND reference_no = ?",
                    ("PurchaseInvoice", existing_invoice_number),
                )
            else:
                cursor.execute(
                    """
                    INSERT INTO purchase_invoices(
                        invoice_number,
                        supplier_id,
                        purchase_order_id,
                        goods_receipt_id,
                        invoice_date,
                        due_date,
                        currency,
                        exchange_rate,
                        subtotal,
                        discount_total,
                        vat_total,
                        grand_total,
                        status,
                        notes,
                        created_by,
                        created_at,
                        updated_at
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        invoice_number,
                        supplier_id,
                        purchase_order_id or None,
                        goods_receipt_id,
                        invoice_date,
                        due_date or None,
                        currency or "USD",
                        exchange_rate,
                        subtotal,
                        discount_total,
                        vat_total,
                        grand_total,
                        "Posted",
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
                row_warehouse = ""
                if int(goods_receipt_id or 0) > 0 and int(item.get("goods_receipt_item_id") or 0) > 0:
                    cursor.execute(
                        "SELECT COALESCE(warehouse, '') FROM goods_receipt_items WHERE id = ?",
                        (int(item.get("goods_receipt_item_id") or 0),),
                    )
                    wh_row = cursor.fetchone()
                    row_warehouse = str((wh_row[0] if wh_row else "") or "")

                cursor.execute(
                    """
                    INSERT INTO purchase_invoice_items(
                        invoice_id,
                        goods_receipt_item_id,
                        stock_id,
                        quantity,
                        unit,
                        unit_price,
                        discount_percent,
                        vat_percent,
                        line_total,
                        created_at
                    ) VALUES(?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        invoice_id,
                        int(item.get("goods_receipt_item_id") or 0),
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
                        "UPDATE stoklar SET current_stock = COALESCE(current_stock, 0) + ? WHERE id = ?",
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
                            "PURCHASE",
                            quantity,
                            "PurchaseInvoice",
                            invoice_number,
                            invoice_date,
                            row_warehouse,
                            f"Purchase Invoice {invoice_number} Line {invoice_line_id}",
                            now_value,
                        ),
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
                    supplier_id,
                    invoice_date,
                    "Invoice",
                    "PurchaseInvoice",
                    invoice_number,
                    grand_total,
                    currency or "USD",
                    exchange_rate,
                    f"Purchase invoice {invoice_number}",
                    "Posted",
                    now_value,
                ),
            )

            conn.commit()

        cls._update_goods_receipt_invoice_status(goods_receipt_id)
        return invoice_id

    @classmethod
    def cancel_invoice(cls, invoice_number: str) -> None:
        with cls()._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT goods_receipt_id FROM purchase_invoices WHERE invoice_number = ?",
                (invoice_number,),
            )
            row = cursor.fetchone()
            if row is None:
                return
            goods_receipt_id = int(row[0])

            cursor.execute(
                """
                SELECT pii.stock_id, COALESCE(pii.quantity, 0)
                FROM purchase_invoice_items pii
                INNER JOIN purchase_invoices pi ON pi.id = pii.invoice_id
                WHERE pi.invoice_number = ?
                """,
                (invoice_number,),
            )
            stock_rows = cursor.fetchall()
            for stock_id, qty in stock_rows:
                sid = int(stock_id or 0)
                amount = float(qty or 0)
                if sid > 0 and amount > 0:
                    cursor.execute(
                        "UPDATE stoklar SET current_stock = COALESCE(current_stock, 0) - ? WHERE id = ?",
                        (amount, sid),
                    )

            cursor.execute(
                "UPDATE purchase_invoices SET status = ?, updated_at = ? WHERE invoice_number = ?",
                ("Cancelled", cls._now(), invoice_number),
            )
            cursor.execute(
                """
                UPDATE supplier_account_movements
                SET status = ?
                WHERE reference_type = ? AND reference_no = ?
                """,
                ("Cancelled", "PurchaseInvoice", invoice_number),
            )
            cursor.execute(
                "DELETE FROM stock_movements WHERE reference_type = ? AND reference_no = ?",
                ("PurchaseInvoice", invoice_number),
            )
            conn.commit()

        cls._update_goods_receipt_invoice_status(goods_receipt_id)

    @classmethod
    def list_cari_movements(cls) -> List[Dict[str, Any]]:
        with cls()._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT
                    COALESCE(sam.movement_date, '') AS belge_tarihi,
                    CASE
                        WHEN LOWER(COALESCE(sam.movement_type, '')) = 'invoice' THEN 'Alış Faturası'
                        ELSE COALESCE(sam.movement_type, '')
                    END AS belge_tipi,
                    COALESCE(sam.reference_no, '') AS belge_no,
                    COALESCE(c.firma_unvani, s.company_name, '') AS cari,
                    CASE
                        WHEN LOWER(COALESCE(sam.movement_type, '')) = 'invoice' THEN COALESCE(sam.amount, 0)
                        ELSE 0
                    END AS borc,
                    CASE
                        WHEN LOWER(COALESCE(sam.movement_type, '')) IN ('payment', 'credit') THEN COALESCE(sam.amount, 0)
                        ELSE 0
                    END AS alacak,
                    COALESCE(sam.description, '') AS aciklama,
                    sam.id AS movement_id
                FROM supplier_account_movements sam
                LEFT JOIN suppliers s ON s.id = sam.supplier_id
                LEFT JOIN cariler c ON (
                    LOWER(COALESCE(c.cari_kodu, '')) = LOWER(COALESCE(s.supplier_code, ''))
                    OR LOWER(COALESCE(c.firma_unvani, '')) = LOWER(COALESCE(s.company_name, ''))
                )
                WHERE LOWER(COALESCE(sam.status, '')) != 'cancelled'
                ORDER BY COALESCE(sam.movement_date, ''), sam.id
                """
            )
            rows = cls._rows_to_dicts(cursor, cursor.fetchall())

        running_balances: Dict[str, float] = {}
        normalized: List[Dict[str, Any]] = []
        for row in rows:
            cari_name = str(row.get("cari") or "").strip() or "-"
            borc = float(row.get("borc") or 0)
            alacak = float(row.get("alacak") or 0)
            running_balances[cari_name] = float(running_balances.get(cari_name, 0)) + borc - alacak

            payload = dict(row)
            payload["cari"] = cari_name
            payload["bakiye"] = running_balances[cari_name]
            normalized.append(payload)

        return normalized

    @classmethod
    def resolve_supplier_id_for_cari(cls, cari_kodu: str, firma_unvani: str) -> int:
        code = str(cari_kodu or "").strip()
        company = str(firma_unvani or "").strip()

        with cls()._connect() as conn:
            cursor = conn.cursor()
            if code:
                cursor.execute(
                    "SELECT id FROM suppliers WHERE LOWER(COALESCE(supplier_code, '')) = LOWER(?)",
                    (code,),
                )
                row = cursor.fetchone()
                if row is not None:
                    return int(row[0])

            if company:
                cursor.execute(
                    "SELECT id FROM suppliers WHERE LOWER(COALESCE(company_name, '')) = LOWER(?)",
                    (company,),
                )
                row = cursor.fetchone()
                if row is not None:
                    return int(row[0])

        return 0

    @classmethod
    def current_balance_for_supplier(cls, supplier_id: int) -> float:
        if supplier_id <= 0:
            return 0.0

        with cls()._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT
                    COALESCE(SUM(
                        CASE
                            WHEN LOWER(COALESCE(movement_type, '')) IN ('invoice', 'debit') THEN COALESCE(amount, 0)
                            WHEN LOWER(COALESCE(movement_type, '')) IN ('payment', 'credit') THEN -COALESCE(amount, 0)
                            ELSE 0
                        END
                    ), 0)
                FROM supplier_account_movements
                WHERE supplier_id = ?
                  AND LOWER(COALESCE(status, '')) != 'cancelled'
                """,
                (supplier_id,),
            )
            return float(cursor.fetchone()[0] or 0)

    @classmethod
    def ledger_for_supplier(
        cls,
        supplier_id: int,
        start_date: str,
        end_date: str,
    ) -> Dict[str, Any]:
        if supplier_id <= 0:
            return {
                "rows": [],
                "opening_balance": 0.0,
                "total_debit": 0.0,
                "total_credit": 0.0,
                "closing_balance": 0.0,
            }

        with cls()._connect() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT
                    COALESCE(SUM(
                        CASE
                            WHEN LOWER(COALESCE(movement_type, '')) IN ('invoice', 'debit') THEN COALESCE(amount, 0)
                            WHEN LOWER(COALESCE(movement_type, '')) IN ('payment', 'credit') THEN -COALESCE(amount, 0)
                            ELSE 0
                        END
                    ), 0)
                FROM supplier_account_movements
                WHERE supplier_id = ?
                  AND LOWER(COALESCE(status, '')) != 'cancelled'
                  AND DATE(COALESCE(movement_date, '')) < DATE(?)
                """,
                (supplier_id, start_date),
            )
            opening_balance = float(cursor.fetchone()[0] or 0)

            cursor.execute(
                """
                SELECT
                    sam.id,
                    COALESCE(sam.movement_date, '') AS movement_date,
                    LOWER(COALESCE(sam.movement_type, '')) AS movement_type,
                    COALESCE(sam.reference_type, '') AS reference_type,
                    COALESCE(sam.reference_no, '') AS reference_no,
                    COALESCE(sam.amount, 0) AS amount,
                    COALESCE(sam.currency, 'USD') AS currency,
                    COALESCE(sam.description, '') AS description,
                    COALESCE(sam.status, '') AS status,
                    COALESCE(s.company_name, '') AS company_name
                FROM supplier_account_movements sam
                LEFT JOIN suppliers s ON s.id = sam.supplier_id
                WHERE sam.supplier_id = ?
                  AND LOWER(COALESCE(sam.status, '')) != 'cancelled'
                  AND DATE(COALESCE(sam.movement_date, '')) BETWEEN DATE(?) AND DATE(?)
                ORDER BY DATE(COALESCE(sam.movement_date, '')) ASC, sam.id ASC
                """,
                (supplier_id, start_date, end_date),
            )
            rows = cls._rows_to_dicts(cursor, cursor.fetchall())

        running_balance = opening_balance
        total_debit = 0.0
        total_credit = 0.0
        normalized_rows: List[Dict[str, Any]] = []

        for row in rows:
            movement_type = str(row.get("movement_type") or "").strip().lower()
            amount = float(row.get("amount") or 0)

            if movement_type in ("invoice", "debit"):
                debit = amount
                credit = 0.0
            elif movement_type in ("payment", "credit"):
                debit = 0.0
                credit = amount
            else:
                debit = amount if amount > 0 else 0.0
                credit = abs(amount) if amount < 0 else 0.0

            running_balance += debit - credit
            total_debit += debit
            total_credit += credit

            document_type_map = {
                "invoice": "Alış Faturası",
                "payment": "Ödeme",
                "credit": "Tahsilat",
                "debit": "Borç Dekontu",
            }

            normalized_rows.append(
                {
                    "date": str(row.get("movement_date") or ""),
                    "document_type": document_type_map.get(movement_type, movement_type.title() or "Belge"),
                    "document_no": str(row.get("reference_no") or ""),
                    "description": str(row.get("description") or ""),
                    "debit": debit,
                    "credit": credit,
                    "running_balance": running_balance,
                    "currency": str(row.get("currency") or "USD"),
                    "user": "SYSTEM",
                    "status": str(row.get("status") or ""),
                    "reference_type": str(row.get("reference_type") or ""),
                    "movement_id": int(row.get("id") or 0),
                }
            )

        return {
            "rows": normalized_rows,
            "opening_balance": opening_balance,
            "total_debit": total_debit,
            "total_credit": total_credit,
            "closing_balance": opening_balance + total_debit - total_credit,
        }

    @classmethod
    def _update_goods_receipt_invoice_status(cls, goods_receipt_id: int) -> None:
        with cls()._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COALESCE(SUM(received_qty), 0) FROM goods_receipt_items WHERE receipt_id = ?",
                (goods_receipt_id,),
            )
            received_total = float(cursor.fetchone()[0] or 0)

            cursor.execute(
                """
                SELECT COALESCE(SUM(pii.quantity), 0)
                FROM purchase_invoice_items pii
                INNER JOIN purchase_invoices pi ON pi.id = pii.invoice_id
                WHERE pi.goods_receipt_id = ?
                  AND LOWER(COALESCE(pi.status, '')) != 'cancelled'
                """,
                (goods_receipt_id,),
            )
            invoiced_total = float(cursor.fetchone()[0] or 0)

            if invoiced_total <= 0:
                new_status = "Posted"
            elif invoiced_total < received_total:
                new_status = "Partially Invoiced"
            else:
                new_status = "Invoiced"

            cursor.execute(
                "UPDATE goods_receipts SET status = ?, updated_at = ? WHERE id = ?",
                (new_status, cls._now(), goods_receipt_id),
            )
            conn.commit()
