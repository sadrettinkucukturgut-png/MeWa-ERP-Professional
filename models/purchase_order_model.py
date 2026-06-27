from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.crud_base import BaseCrud


class PurchaseOrderModel(BaseCrud):
    db_path = str(Path(__file__).resolve().parent.parent / "database" / "mewa.db")
    table_name = "purchase_orders"
    id_field = "id"

    @staticmethod
    def _now() -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def _rows_to_dicts(cursor, rows) -> List[Dict[str, Any]]:
        columns = [column[1] for column in cursor.description] if cursor.description else []
        return [dict(zip(columns, row)) for row in rows]

    @staticmethod
    def _compose_notes(reference_no: str, notes: str) -> str:
        reference = (reference_no or "").strip()
        body = (notes or "").strip()
        if reference:
            return f"REF:{reference}\n{body}".strip()
        return body

    @staticmethod
    def _split_notes(raw_notes: str) -> Dict[str, str]:
        value = raw_notes or ""
        lines = value.splitlines()
        reference_no = ""
        if lines and lines[0].startswith("REF:"):
            reference_no = lines[0][4:].strip()
            value = "\n".join(lines[1:]).strip()
        return {"reference_no": reference_no, "notes": value}

    @classmethod
    def siparis_numarasi_uret(cls) -> str:
        today_prefix = datetime.now().strftime("PO-%Y%m%d-")
        with cls()._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"""
                SELECT order_number
                FROM {cls.table_name}
                WHERE order_number LIKE ?
                ORDER BY order_number DESC
                LIMIT 1
                """,
                (f"{today_prefix}%",),
            )
            row = cursor.fetchone()

        if not row or not row[0]:
            return f"{today_prefix}0001"

        last_number = str(row[0]).split("-")[-1]
        try:
            next_no = int(last_number) + 1
        except ValueError:
            next_no = 1
        return f"{today_prefix}{next_no:04d}"

    @classmethod
    def listele(cls, keyword: str = "") -> List[Dict[str, Any]]:
        where_clause = ""
        params: List[Any] = []

        if keyword and keyword.strip():
            token = f"%{keyword.strip().lower()}%"
            where_clause = """
                WHERE LOWER(po.order_number) LIKE ?
                   OR LOWER(COALESCE(s.company_name, '')) LIKE ?
                   OR LOWER(COALESCE(po.currency, '')) LIKE ?
                   OR LOWER(COALESCE(po.status, '')) LIKE ?
                   OR LOWER(COALESCE(po.order_date, '')) LIKE ?
                   OR LOWER(COALESCE(po.delivery_date, '')) LIKE ?
            """
            params = [token, token, token, token, token, token]

        with cls()._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"""
                SELECT
                    po.id,
                    po.order_number,
                    po.order_date,
                    COALESCE(s.company_name, '') AS supplier_name,
                    po.currency,
                    po.status,
                    COALESCE(SUM(poi.line_total), 0) AS total_amount,
                    po.delivery_date,
                    po.supplier_id,
                    po.exchange_rate,
                    po.notes,
                    po.created_at,
                    po.updated_at
                FROM purchase_orders po
                LEFT JOIN suppliers s ON s.id = po.supplier_id
                LEFT JOIN purchase_order_items poi ON poi.order_id = po.id
                {where_clause}
                GROUP BY po.id
                ORDER BY po.order_date DESC, po.id DESC
                """,
                params,
            )
            rows = cls._rows_to_dicts(cursor, cursor.fetchall())

        for row in rows:
            parsed = cls._split_notes(str(row.get("notes") or ""))
            row["reference_no"] = parsed["reference_no"]
            row["notes"] = parsed["notes"]
            row["created_by"] = "SYSTEM"
        return rows

    @classmethod
    def detay_getir(cls, order_number: str) -> Optional[Dict[str, Any]]:
        with cls()._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT
                    po.id,
                    po.order_number,
                    po.supplier_id,
                    COALESCE(s.company_name, '') AS supplier_name,
                    po.order_date,
                    po.delivery_date,
                    po.currency,
                    po.exchange_rate,
                    po.status,
                    po.notes,
                    po.created_at,
                    po.updated_at
                FROM purchase_orders po
                LEFT JOIN suppliers s ON s.id = po.supplier_id
                WHERE po.order_number = ?
                """,
                (order_number,),
            )
            header_rows = cls._rows_to_dicts(cursor, cursor.fetchall())
            if not header_rows:
                return None

            header = header_rows[0]
            parsed = cls._split_notes(str(header.get("notes") or ""))
            header["reference_no"] = parsed["reference_no"]
            header["notes"] = parsed["notes"]
            header["created_by"] = "SYSTEM"

            cursor.execute(
                """
                SELECT
                    poi.id,
                    poi.stock_id,
                    COALESCE(st.stock_code, '') AS stock_code,
                    COALESCE(st.barcode, '') AS barcode,
                    COALESCE(st.product_name, '') AS product_name,
                    poi.unit,
                    poi.quantity,
                    poi.unit_price,
                    poi.discount_percent,
                    poi.vat_percent,
                    poi.line_total
                FROM purchase_order_items poi
                LEFT JOIN stoklar st ON st.id = poi.stock_id
                WHERE poi.order_id = ?
                ORDER BY poi.id
                """,
                (int(header["id"]),),
            )
            header["items"] = cls._rows_to_dicts(cursor, cursor.fetchall())
            return header

    @classmethod
    def kaydet(
        cls,
        order_number: str,
        supplier_id: int,
        order_date: str,
        delivery_date: str,
        currency: str,
        exchange_rate: float,
        status: str,
        reference_no: str,
        notes: str,
        items: List[Dict[str, Any]],
        existing_order_number: Optional[str] = None,
    ) -> int:
        now_value = cls._now()
        payload_notes = cls._compose_notes(reference_no, notes)

        with cls()._connect() as conn:
            cursor = conn.cursor()

            if existing_order_number:
                cursor.execute(
                    f"SELECT id FROM {cls.table_name} WHERE order_number = ?",
                    (existing_order_number,),
                )
                row = cursor.fetchone()
                if row is None:
                    raise ValueError("Purchase order not found")
                order_id = int(row[0])

                cursor.execute(
                    f"""
                    UPDATE {cls.table_name}
                    SET
                        order_number = ?,
                        supplier_id = ?,
                        order_date = ?,
                        delivery_date = ?,
                        currency = ?,
                        exchange_rate = ?,
                        status = ?,
                        notes = ?,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        order_number,
                        supplier_id,
                        order_date,
                        delivery_date or None,
                        currency or "USD",
                        exchange_rate,
                        status or "Draft",
                        payload_notes,
                        now_value,
                        order_id,
                    ),
                )

                cursor.execute("DELETE FROM purchase_order_items WHERE order_id = ?", (order_id,))
            else:
                cursor.execute(
                    f"""
                    INSERT INTO {cls.table_name}(
                        order_number,
                        supplier_id,
                        order_date,
                        delivery_date,
                        currency,
                        exchange_rate,
                        status,
                        notes,
                        created_at,
                        updated_at
                    ) VALUES(?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        order_number,
                        supplier_id,
                        order_date,
                        delivery_date or None,
                        currency or "USD",
                        exchange_rate,
                        status or "Draft",
                        payload_notes,
                        now_value,
                        now_value,
                    ),
                )
                order_id = int(cursor.lastrowid)

            for item in items:
                cursor.execute(
                    """
                    INSERT INTO purchase_order_items(
                        order_id,
                        stock_id,
                        quantity,
                        unit,
                        unit_price,
                        currency,
                        exchange_rate,
                        discount_percent,
                        vat_percent,
                        line_total
                    ) VALUES(?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        order_id,
                        int(item.get("stock_id") or 0),
                        float(item.get("quantity") or 0),
                        str(item.get("unit") or ""),
                        float(item.get("unit_price") or 0),
                        currency or "USD",
                        exchange_rate,
                        float(item.get("discount_percent") or 0),
                        float(item.get("vat_percent") or 0),
                        float(item.get("line_total") or 0),
                    ),
                )

            conn.commit()
            return order_id

    @classmethod
    def iptal_et(cls, order_number: str) -> None:
        with cls()._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"UPDATE {cls.table_name} SET status = ?, updated_at = ? WHERE order_number = ?",
                ("Cancelled", cls._now(), order_number),
            )
            conn.commit()

    @classmethod
    def ekle(
        cls,
        order_number: str,
        supplier_id: int,
        order_date: str,
        delivery_date: str = "",
        currency: str = "USD",
        exchange_rate: float = 1.0,
        status: str = "Draft",
        notes: str = "",
    ) -> int:
        now_value = cls._now()
        return cls().insert(
            {
                "order_number": order_number,
                "supplier_id": supplier_id,
                "order_date": order_date,
                "delivery_date": delivery_date or None,
                "currency": currency or "USD",
                "exchange_rate": exchange_rate,
                "status": status or "Draft",
                "notes": notes,
                "created_at": now_value,
                "updated_at": now_value,
            }
        )

    @classmethod
    def getir(cls, order_number: str) -> Optional[Dict[str, Any]]:
        with cls()._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"SELECT * FROM {cls.table_name} WHERE order_number = ?",
                (order_number,),
            )
            rows = cls._rows_to_dicts(cursor, cursor.fetchall())
            return rows[0] if rows else None

    @classmethod
    def guncelle(
        cls,
        existing_order_number: str,
        order_number: str,
        supplier_id: int,
        order_date: str,
        delivery_date: str = "",
        currency: str = "USD",
        exchange_rate: float = 1.0,
        status: str = "Draft",
        notes: str = "",
    ) -> None:
        record = cls.getir(existing_order_number)
        if record is None:
            raise ValueError("Purchase order not found")

        cls().update(
            int(record["id"]),
            {
                "order_number": order_number or existing_order_number,
                "supplier_id": supplier_id,
                "order_date": order_date,
                "delivery_date": delivery_date or None,
                "currency": currency or "USD",
                "exchange_rate": exchange_rate,
                "status": status or "Draft",
                "notes": notes,
                "updated_at": cls._now(),
            },
        )

    @classmethod
    def sil(cls, order_number: str) -> None:
        cls.iptal_et(order_number)

    @classmethod
    def tum_siparisler(cls) -> List[Dict[str, Any]]:
        return cls().load_all(order_by="order_date DESC, id DESC")

    @classmethod
    def ara(cls, keyword: str = "", status: str = "") -> List[Dict[str, Any]]:
        if not keyword and not status:
            return cls.tum_siparisler()

        where_parts: List[str] = []
        params: List[Any] = []

        if keyword and keyword.strip():
            keyword_value = f"%{keyword.strip().lower()}%"
            where_parts.append(
                "(LOWER(order_number) LIKE ? OR LOWER(notes) LIKE ? OR CAST(supplier_id AS TEXT) LIKE ?)"
            )
            params.extend([keyword_value, keyword_value, keyword_value])

        if status and status.strip():
            where_parts.append("LOWER(status) = ?")
            params.append(status.strip().lower())

        where_sql = " AND ".join(where_parts)
        query = f"SELECT * FROM {cls.table_name}"
        if where_sql:
            query += f" WHERE {where_sql}"
        query += " ORDER BY order_date DESC, id DESC"

        with cls()._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return cls._rows_to_dicts(cursor, cursor.fetchall())

    @classmethod
    def order_number_exists(cls, order_number: str, exclude_order_number: Optional[str] = None) -> bool:
        if not order_number:
            return False

        with cls()._connect() as conn:
            cursor = conn.cursor()
            if exclude_order_number:
                cursor.execute(
                    f"SELECT 1 FROM {cls.table_name} WHERE order_number = ? AND order_number != ?",
                    (order_number, exclude_order_number),
                )
            else:
                cursor.execute(
                    f"SELECT 1 FROM {cls.table_name} WHERE order_number = ?",
                    (order_number,),
                )
            return cursor.fetchone() is not None

    @classmethod
    def kalem_ekle(
        cls,
        order_id: int,
        stock_id: int,
        quantity: float,
        unit: str,
        unit_price: float,
        currency: str = "USD",
        exchange_rate: float = 1.0,
        discount_percent: float = 0.0,
        vat_percent: float = 0.0,
        line_total: float = 0.0,
    ) -> int:
        with cls()._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO purchase_order_items(
                    order_id,
                    stock_id,
                    quantity,
                    unit,
                    unit_price,
                    currency,
                    exchange_rate,
                    discount_percent,
                    vat_percent,
                    line_total
                )
                VALUES(?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    order_id,
                    stock_id,
                    quantity,
                    unit,
                    unit_price,
                    currency or "USD",
                    exchange_rate,
                    discount_percent,
                    vat_percent,
                    line_total,
                ),
            )
            conn.commit()
            return int(cursor.lastrowid)

    @classmethod
    def kalemleri_getir(cls, order_id: int) -> List[Dict[str, Any]]:
        with cls()._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT *
                FROM purchase_order_items
                WHERE order_id = ?
                ORDER BY id
                """,
                (order_id,),
            )
            return cls._rows_to_dicts(cursor, cursor.fetchall())

    @classmethod
    def kalem_guncelle(
        cls,
        item_id: int,
        stock_id: int,
        quantity: float,
        unit: str,
        unit_price: float,
        currency: str = "USD",
        exchange_rate: float = 1.0,
        discount_percent: float = 0.0,
        vat_percent: float = 0.0,
        line_total: float = 0.0,
    ) -> None:
        with cls()._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE purchase_order_items
                SET
                    stock_id = ?,
                    quantity = ?,
                    unit = ?,
                    unit_price = ?,
                    currency = ?,
                    exchange_rate = ?,
                    discount_percent = ?,
                    vat_percent = ?,
                    line_total = ?
                WHERE id = ?
                """,
                (
                    stock_id,
                    quantity,
                    unit,
                    unit_price,
                    currency or "USD",
                    exchange_rate,
                    discount_percent,
                    vat_percent,
                    line_total,
                    item_id,
                ),
            )
            conn.commit()

    @classmethod
    def kalem_sil(cls, item_id: int) -> None:
        with cls()._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM purchase_order_items WHERE id = ?", (item_id,))
            conn.commit()

    @classmethod
    def siparis_kalemlerini_sil(cls, order_id: int) -> None:
        with cls()._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM purchase_order_items WHERE order_id = ?", (order_id,))
            conn.commit()
