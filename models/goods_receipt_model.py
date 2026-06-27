from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.crud_base import BaseCrud


class GoodsReceiptModel(BaseCrud):
    db_path = str(Path(__file__).resolve().parent.parent / "database" / "mewa.db")
    table_name = "goods_receipts"
    id_field = "id"

    @staticmethod
    def _now() -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def _rows_to_dicts(cursor, rows) -> List[Dict[str, Any]]:
        columns = [column[0] for column in cursor.description] if cursor.description else []
        return [dict(zip(columns, row)) for row in rows]

    @classmethod
    def receipt_number_generate(cls) -> str:
        prefix = datetime.now().strftime("GR-%Y%m%d-")
        with cls()._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT receipt_number
                FROM goods_receipts
                WHERE receipt_number LIKE ?
                ORDER BY receipt_number DESC
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
    def purchase_orders_lookup(cls) -> List[Dict[str, Any]]:
        with cls()._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT
                    po.id,
                    po.order_number,
                    po.supplier_id,
                    COALESCE(s.company_name, '') AS supplier_name,
                    po.status
                FROM purchase_orders po
                LEFT JOIN suppliers s ON s.id = po.supplier_id
                WHERE LOWER(COALESCE(po.status, '')) != 'cancelled'
                ORDER BY po.order_date DESC, po.id DESC
                """
            )
            return cls._rows_to_dicts(cursor, cursor.fetchall())

    @classmethod
    def purchase_order_items_remaining(cls, purchase_order_id: int) -> List[Dict[str, Any]]:
        with cls()._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT
                    poi.id AS purchase_order_item_id,
                    poi.stock_id,
                    COALESCE(st.stock_code, '') AS stock_code,
                    COALESCE(st.barcode, '') AS barcode,
                    COALESCE(st.product_name, '') AS product_name,
                    COALESCE(poi.unit, '') AS unit,
                    COALESCE(poi.quantity, 0) AS ordered_qty,
                    COALESCE(SUM(
                        CASE
                            WHEN LOWER(COALESCE(gr.status, '')) = 'cancelled' THEN 0
                            ELSE gri.received_qty
                        END
                    ), 0) AS total_received
                FROM purchase_order_items poi
                LEFT JOIN stoklar st ON st.id = poi.stock_id
                LEFT JOIN goods_receipt_items gri ON gri.purchase_order_item_id = poi.id
                LEFT JOIN goods_receipts gr ON gr.id = gri.receipt_id
                WHERE poi.order_id = ?
                GROUP BY poi.id
                ORDER BY poi.id
                """,
                (purchase_order_id,),
            )
            rows = cls._rows_to_dicts(cursor, cursor.fetchall())

        for row in rows:
            ordered = float(row.get("ordered_qty") or 0)
            received = float(row.get("total_received") or 0)
            row["remaining_qty"] = max(ordered - received, 0)
        return rows

    @classmethod
    def list_receipts(cls, keyword: str = "") -> List[Dict[str, Any]]:
        params: List[Any] = []
        where_sql = ""
        if keyword and keyword.strip():
            token = f"%{keyword.strip().lower()}%"
            where_sql = """
                WHERE LOWER(gr.receipt_number) LIKE ?
                   OR LOWER(COALESCE(po.order_number, '')) LIKE ?
                   OR LOWER(COALESCE(s.company_name, '')) LIKE ?
                   OR LOWER(COALESCE(gr.warehouse, '')) LIKE ?
                   OR LOWER(COALESCE(gr.status, '')) LIKE ?
            """
            params = [token, token, token, token, token]

        with cls()._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"""
                SELECT
                    gr.id,
                    gr.receipt_number,
                    COALESCE(po.order_number, '') AS purchase_order,
                    COALESCE(s.company_name, '') AS supplier,
                    gr.receipt_date,
                    COALESCE(gr.warehouse, '') AS warehouse,
                    COALESCE(gr.status, 'Posted') AS status,
                    COALESCE(SUM(gri.received_qty), 0) AS total_quantity,
                    COALESCE(gr.created_by, 'SYSTEM') AS created_by,
                    gr.purchase_order_id,
                    gr.supplier_id,
                    gr.notes
                FROM goods_receipts gr
                LEFT JOIN purchase_orders po ON po.id = gr.purchase_order_id
                LEFT JOIN suppliers s ON s.id = gr.supplier_id
                LEFT JOIN goods_receipt_items gri ON gri.receipt_id = gr.id
                {where_sql}
                GROUP BY gr.id
                ORDER BY gr.receipt_date DESC, gr.id DESC
                """,
                params,
            )
            return cls._rows_to_dicts(cursor, cursor.fetchall())

    @classmethod
    def receipt_detail(cls, receipt_number: str) -> Optional[Dict[str, Any]]:
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
                    gr.warehouse,
                    gr.receipt_date,
                    gr.status,
                    gr.notes,
                    COALESCE(gr.created_by, 'SYSTEM') AS created_by
                FROM goods_receipts gr
                LEFT JOIN purchase_orders po ON po.id = gr.purchase_order_id
                LEFT JOIN suppliers s ON s.id = gr.supplier_id
                WHERE gr.receipt_number = ?
                """,
                (receipt_number,),
            )
            headers = cls._rows_to_dicts(cursor, cursor.fetchall())
            if not headers:
                return None

            header = headers[0]
            cursor.execute(
                """
                SELECT
                    gri.id,
                    gri.purchase_order_item_id,
                    gri.stock_id,
                    COALESCE(st.stock_code, '') AS stock_code,
                    COALESCE(st.barcode, '') AS barcode,
                    COALESCE(st.product_name, '') AS product_name,
                    COALESCE(gri.ordered_qty, 0) AS ordered_qty,
                    COALESCE(gri.received_qty, 0) AS received_qty,
                    COALESCE(gri.remaining_qty, 0) AS remaining_qty,
                    COALESCE(gri.unit, '') AS unit,
                    COALESCE(gri.warehouse, '') AS warehouse
                FROM goods_receipt_items gri
                LEFT JOIN stoklar st ON st.id = gri.stock_id
                WHERE gri.receipt_id = ?
                ORDER BY gri.id
                """,
                (int(header["id"]),),
            )
            header["items"] = cls._rows_to_dicts(cursor, cursor.fetchall())
            return header

    @classmethod
    def save_receipt(
        cls,
        receipt_number: str,
        purchase_order_id: int,
        supplier_id: int,
        warehouse: str,
        receipt_date: str,
        notes: str,
        items: List[Dict[str, Any]],
        created_by: str = "SYSTEM",
        existing_receipt_number: Optional[str] = None,
    ) -> int:
        now_value = cls._now()
        with cls()._connect() as conn:
            cursor = conn.cursor()

            if existing_receipt_number:
                cursor.execute(
                    "SELECT id FROM goods_receipts WHERE receipt_number = ?",
                    (existing_receipt_number,),
                )
                row = cursor.fetchone()
                if row is None:
                    raise ValueError("Goods receipt not found")
                receipt_id = int(row[0])

                cursor.execute(
                    """
                    UPDATE goods_receipts
                    SET
                        receipt_number = ?,
                        purchase_order_id = ?,
                        supplier_id = ?,
                        warehouse = ?,
                        receipt_date = ?,
                        notes = ?,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        receipt_number,
                        purchase_order_id,
                        supplier_id,
                        warehouse,
                        receipt_date,
                        notes,
                        now_value,
                        receipt_id,
                    ),
                )
            else:
                cursor.execute(
                    """
                    INSERT INTO goods_receipts(
                        receipt_number,
                        purchase_order_id,
                        supplier_id,
                        warehouse,
                        receipt_date,
                        status,
                        notes,
                        created_by,
                        created_at,
                        updated_at
                    ) VALUES(?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        receipt_number,
                        purchase_order_id,
                        supplier_id,
                        warehouse,
                        receipt_date,
                        "Posted",
                        notes,
                        created_by or "SYSTEM",
                        now_value,
                        now_value,
                    ),
                )
                receipt_id = int(cursor.lastrowid)

            if existing_receipt_number:
                return receipt_id

            for item in items:
                purchase_order_item_id = int(item.get("purchase_order_item_id") or 0)
                stock_id = int(item.get("stock_id") or 0)
                ordered_qty = float(item.get("ordered_qty") or 0)
                received_qty = float(item.get("received_qty") or 0)
                if received_qty <= 0:
                    continue
                remaining_qty = float(item.get("remaining_qty") or 0)
                unit = str(item.get("unit") or "")
                row_warehouse = str(item.get("warehouse") or warehouse or "")

                cursor.execute(
                    """
                    INSERT INTO goods_receipt_items(
                        receipt_id,
                        purchase_order_item_id,
                        stock_id,
                        ordered_qty,
                        received_qty,
                        remaining_qty,
                        unit,
                        warehouse,
                        created_at
                    ) VALUES(?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        receipt_id,
                        purchase_order_item_id,
                        stock_id,
                        ordered_qty,
                        received_qty,
                        remaining_qty,
                        unit,
                        row_warehouse,
                        now_value,
                    ),
                )

                cursor.execute(
                    "UPDATE stoklar SET current_stock = COALESCE(current_stock, 0) + ? WHERE id = ?",
                    (received_qty, stock_id),
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
                        "GoodsReceipt",
                        received_qty,
                        "GoodsReceipt",
                        receipt_number,
                        receipt_date,
                        row_warehouse,
                        notes,
                        now_value,
                    ),
                )

            conn.commit()

        cls._update_purchase_order_receipt_status(purchase_order_id)
        return receipt_id

    @classmethod
    def cancel_receipt(cls, receipt_number: str) -> None:
        with cls()._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT purchase_order_id FROM goods_receipts WHERE receipt_number = ?",
                (receipt_number,),
            )
            row = cursor.fetchone()
            if row is None:
                return
            purchase_order_id = int(row[0])

            cursor.execute(
                "UPDATE goods_receipts SET status = ?, updated_at = ? WHERE receipt_number = ?",
                ("Cancelled", cls._now(), receipt_number),
            )
            conn.commit()

        cls._update_purchase_order_receipt_status(purchase_order_id)

    @classmethod
    def _update_purchase_order_receipt_status(cls, purchase_order_id: int) -> None:
        with cls()._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COALESCE(SUM(quantity), 0) FROM purchase_order_items WHERE order_id = ?",
                (purchase_order_id,),
            )
            ordered_total = float(cursor.fetchone()[0] or 0)

            cursor.execute(
                """
                SELECT COALESCE(SUM(gri.received_qty), 0)
                FROM goods_receipt_items gri
                INNER JOIN goods_receipts gr ON gr.id = gri.receipt_id
                WHERE gr.purchase_order_id = ?
                  AND LOWER(COALESCE(gr.status, '')) != 'cancelled'
                """,
                (purchase_order_id,),
            )
            received_total = float(cursor.fetchone()[0] or 0)

            if received_total <= 0:
                new_status = "Draft"
            elif received_total < ordered_total:
                new_status = "Partial Receipt"
            else:
                new_status = "Completed"

            cursor.execute(
                "UPDATE purchase_orders SET status = ?, updated_at = ? WHERE id = ?",
                (new_status, cls._now(), purchase_order_id),
            )
            conn.commit()
