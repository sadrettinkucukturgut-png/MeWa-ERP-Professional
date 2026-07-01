from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.crud_base import BaseCrud
from models.finance_model import FinanceModel


class PackingListModel(BaseCrud):
    db_path = str(Path(__file__).resolve().parent.parent / "database" / "mewa.db")
    table_name = "packing_lists"
    id_field = "id"

    @staticmethod
    def _now() -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def _rows_to_dicts(cursor, rows) -> List[Dict[str, Any]]:
        columns = [column[0] for column in cursor.description] if cursor.description else []
        return [dict(zip(columns, row)) for row in rows]

    @classmethod
    def _append_history(cls, cursor, packing_list_id: int, event_type: str, event_note: str, created_by: str) -> None:
        cursor.execute(
            """
            INSERT INTO packing_list_history(packing_list_id, event_type, event_note, created_by, created_at)
            VALUES(?,?,?,?,?)
            """,
            (
                int(packing_list_id),
                str(event_type or "").strip() or "Unknown",
                str(event_note or "").strip(),
                str(created_by or "SYSTEM"),
                cls._now(),
            ),
        )

    @classmethod
    def packing_list_number_generate(cls) -> str:
        prefix = datetime.now().strftime("PL-%Y%m%d-")
        with cls()._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT packing_list_number
                FROM packing_lists
                WHERE packing_list_number LIKE ?
                ORDER BY packing_list_number DESC
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
                    "SELECT id FROM cariler WHERE LOWER(COALESCE(cari_kodu, '')) = LOWER(?) LIMIT 1",
                    (code,),
                )
                row = cursor.fetchone()
                if row is not None:
                    return int(row[0])

            cursor.execute(
                "SELECT id FROM cariler WHERE LOWER(COALESCE(firma_unvani, '')) = LOWER(?) LIMIT 1",
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

            cursor.execute(
                """
                INSERT INTO cariler(
                    cari_kodu,
                    firma_unvani,
                    yetkili,
                    telefon,
                    email,
                    vergi_dairesi,
                    vergi_no,
                    ulke,
                    sehir,
                    ilce,
                    adres
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    generated_code,
                    company,
                    company,
                    "",
                    "-",
                    "-",
                    "-",
                    "-",
                    "-",
                    "-",
                    "-",
                ),
            )
            conn.commit()
            return int(cursor.lastrowid)

    @classmethod
    def source_documents(cls, keyword: str = "") -> List[Dict[str, Any]]:
        token = f"%{str(keyword or '').strip().lower()}%"
        use_filter = bool(str(keyword or "").strip())

        rows: List[Dict[str, Any]] = []
        with cls()._connect() as conn:
            cursor = conn.cursor()

            proforma_sql = """
                SELECT
                    'Proforma' AS source_type,
                    ph.proforma_number AS source_number,
                    ph.issue_date AS source_date,
                    COALESCE(c.firma_unvani, '') AS customer_name,
                    COALESCE(c.cari_kodu, '') AS customer_code,
                    COALESCE(ph.currency, 'USD') AS currency,
                    COALESCE(ph.grand_total, 0) AS grand_total,
                    COALESCE(ph.status, 'Draft') AS status
                FROM proforma_headers ph
                LEFT JOIN cariler c ON c.id = ph.customer_id
                WHERE LOWER(COALESCE(ph.status, '')) NOT IN ('cancelled', 'rejected')
            """
            proforma_params: List[Any] = []
            if use_filter:
                proforma_sql += """
                    AND (
                        LOWER(COALESCE(ph.proforma_number, '')) LIKE ?
                        OR LOWER(COALESCE(c.firma_unvani, '')) LIKE ?
                        OR LOWER(COALESCE(c.cari_kodu, '')) LIKE ?
                    )
                """
                proforma_params.extend([token, token, token])
            proforma_sql += " ORDER BY ph.issue_date DESC, ph.id DESC"
            cursor.execute(proforma_sql, proforma_params)
            rows.extend(cls._rows_to_dicts(cursor, cursor.fetchall()))

            sales_sql = """
                SELECT
                    'SalesInvoice' AS source_type,
                    si.invoice_number AS source_number,
                    si.invoice_date AS source_date,
                    COALESCE(c.firma_unvani, '') AS customer_name,
                    COALESCE(c.cari_kodu, '') AS customer_code,
                    COALESCE(si.currency, 'USD') AS currency,
                    COALESCE(si.grand_total, 0) AS grand_total,
                    COALESCE(si.status, 'Posted') AS status
                FROM sales_invoices si
                LEFT JOIN cariler c ON c.id = si.customer_id
                WHERE LOWER(COALESCE(si.status, '')) != 'cancelled'
            """
            sales_params: List[Any] = []
            if use_filter:
                sales_sql += """
                    AND (
                        LOWER(COALESCE(si.invoice_number, '')) LIKE ?
                        OR LOWER(COALESCE(c.firma_unvani, '')) LIKE ?
                        OR LOWER(COALESCE(c.cari_kodu, '')) LIKE ?
                    )
                """
                sales_params.extend([token, token, token])
            sales_sql += " ORDER BY si.invoice_date DESC, si.id DESC"
            cursor.execute(sales_sql, sales_params)
            rows.extend(cls._rows_to_dicts(cursor, cursor.fetchall()))

        rows.sort(key=lambda row: (str(row.get("source_date") or ""), str(row.get("source_number") or "")), reverse=True)
        return rows

    @classmethod
    def source_detail(cls, source_type: str, source_number: str) -> Optional[Dict[str, Any]]:
        stype = str(source_type or "").strip()
        number = str(source_number or "").strip()
        if not stype or not number:
            return None

        with cls()._connect() as conn:
            cursor = conn.cursor()

            if stype == "Proforma":
                cursor.execute(
                    """
                    SELECT
                        ph.id,
                        ph.proforma_number AS source_number,
                        ph.issue_date AS source_date,
                        ph.customer_id,
                        COALESCE(c.cari_kodu, '') AS customer_code,
                        COALESCE(c.firma_unvani, '') AS customer_name,
                        COALESCE(c.adres, '') AS customer_address,
                        COALESCE(c.ulke, '') AS country,
                        COALESCE(c.telefon, '') AS customer_phone,
                        COALESCE(c.email, '') AS customer_email,
                        COALESCE(ph.payment_terms, '') AS payment_terms,
                        COALESCE(ph.delivery_terms, '') AS delivery_terms,
                        COALESCE(ph.currency, 'USD') AS currency,
                        COALESCE(ph.notes, '') AS notes
                    FROM proforma_headers ph
                    LEFT JOIN cariler c ON c.id = ph.customer_id
                    WHERE ph.proforma_number = ?
                    LIMIT 1
                    """,
                    (number,),
                )
                headers = cls._rows_to_dicts(cursor, cursor.fetchall())
                if not headers:
                    return None
                header = headers[0]

                cursor.execute(
                    """
                    SELECT
                        pl.id,
                        pl.stock_id,
                        COALESCE(st.stock_code, '') AS stock_code,
                        COALESCE(st.product_name, '') AS description,
                        COALESCE(st.hs_code, '') AS hs_code,
                        COALESCE(st.unit, '') AS unit,
                        COALESCE(st.weight, 0) AS product_weight,
                        COALESCE(st.brand, '') AS brand,
                        COALESCE(pl.quantity, 0) AS quantity,
                        COALESCE(pl.unit_price, 0) AS unit_price,
                        '' AS remarks
                    FROM proforma_lines pl
                    LEFT JOIN stoklar st ON st.id = pl.stock_id
                    WHERE pl.proforma_id = ?
                    ORDER BY pl.id
                    """,
                    (int(header["id"]),),
                )
                header["items"] = cls._rows_to_dicts(cursor, cursor.fetchall())
                header["source_type"] = "Proforma"
                return header

            if stype == "SalesInvoice":
                cursor.execute(
                    """
                    SELECT
                        si.id,
                        si.invoice_number AS source_number,
                        si.invoice_date AS source_date,
                        si.customer_id,
                        COALESCE(c.cari_kodu, '') AS customer_code,
                        COALESCE(c.firma_unvani, '') AS customer_name,
                        COALESCE(c.adres, '') AS customer_address,
                        COALESCE(c.ulke, '') AS country,
                        COALESCE(c.telefon, '') AS customer_phone,
                        COALESCE(c.email, '') AS customer_email,
                        COALESCE(si.payment_terms, '') AS payment_terms,
                        COALESCE(si.delivery_terms, '') AS delivery_terms,
                        COALESCE(si.currency, 'USD') AS currency,
                        COALESCE(si.notes, '') AS notes,
                        COALESCE(si.source_proforma_number, '') AS source_proforma_number
                    FROM sales_invoices si
                    LEFT JOIN cariler c ON c.id = si.customer_id
                    WHERE si.invoice_number = ?
                    LIMIT 1
                    """,
                    (number,),
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
                        COALESCE(st.product_name, '') AS description,
                        COALESCE(st.hs_code, '') AS hs_code,
                        COALESCE(st.unit, '') AS unit,
                        COALESCE(st.weight, 0) AS product_weight,
                        COALESCE(st.brand, '') AS brand,
                        COALESCE(sii.quantity, 0) AS quantity,
                        COALESCE(sii.unit_price, 0) AS unit_price,
                        '' AS remarks
                    FROM sales_invoice_items sii
                    LEFT JOIN stoklar st ON st.id = sii.stock_id
                    WHERE sii.invoice_id = ?
                    ORDER BY sii.id
                    """,
                    (int(header["id"]),),
                )
                header["items"] = cls._rows_to_dicts(cursor, cursor.fetchall())
                header["source_type"] = "SalesInvoice"
                return header

        return None

    @classmethod
    def list_packing_lists(cls, keyword: str = "") -> List[Dict[str, Any]]:
        params: List[Any] = []
        where_sql = ""
        if keyword and keyword.strip():
            token = f"%{keyword.strip().lower()}%"
            where_sql = """
                WHERE LOWER(COALESCE(pl.packing_list_number, '')) LIKE ?
                   OR LOWER(COALESCE(c.firma_unvani, '')) LIKE ?
                   OR LOWER(COALESCE(pl.invoice_number, '')) LIKE ?
                   OR LOWER(COALESCE(pl.proforma_number, '')) LIKE ?
                   OR LOWER(COALESCE(pl.source_number, '')) LIKE ?
            """
            params = [token, token, token, token, token]

        with cls()._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"""
                SELECT
                    pl.id,
                    pl.packing_list_number,
                    pl.packing_date,
                    COALESCE(c.firma_unvani, '') AS customer_name,
                    COALESCE(c.cari_kodu, '') AS customer_code,
                    COALESCE(pl.invoice_number, '') AS invoice_number,
                    COALESCE(pl.proforma_number, '') AS proforma_number,
                    COALESCE(pl.source_type, '') AS source_type,
                    COALESCE(pl.source_number, '') AS source_number,
                    COALESCE(pl.currency, 'USD') AS currency,
                    COALESCE(pl.total_pallets, 0) AS total_pallets,
                    COALESCE(pl.total_products, 0) AS total_products,
                    COALESCE(pl.total_quantity, 0) AS total_quantity,
                    COALESCE(pl.total_net_weight, 0) AS total_net_weight,
                    COALESCE(pl.total_gross_weight, 0) AS total_gross_weight,
                    COALESCE(pl.status, 'Draft') AS status,
                    COALESCE(pl.created_by, 'SYSTEM') AS created_by
                FROM packing_lists pl
                LEFT JOIN cariler c ON c.id = pl.customer_id
                {where_sql}
                ORDER BY pl.packing_date DESC, pl.id DESC
                """,
                params,
            )
            return cls._rows_to_dicts(cursor, cursor.fetchall())

    @classmethod
    def packing_list_detail(cls, packing_list_number: str) -> Optional[Dict[str, Any]]:
        number = str(packing_list_number or "").strip()
        if not number:
            return None

        with cls()._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT
                    pl.id,
                    pl.packing_list_number,
                    pl.packing_date,
                    pl.customer_id,
                    COALESCE(c.firma_unvani, '') AS customer_name,
                    COALESCE(c.cari_kodu, '') AS customer_code,
                    COALESCE(c.adres, '') AS customer_address,
                    COALESCE(pl.consignee, '') AS consignee,
                    COALESCE(pl.notify_party, '') AS notify_party,
                    COALESCE(pl.invoice_number, '') AS invoice_number,
                    COALESCE(pl.proforma_number, '') AS proforma_number,
                    COALESCE(pl.container_no, '') AS container_no,
                    COALESCE(pl.seal_no, '') AS seal_no,
                    COALESCE(pl.country, '') AS country,
                    COALESCE(pl.port_of_loading, '') AS port_of_loading,
                    COALESCE(pl.port_of_discharge, '') AS port_of_discharge,
                    COALESCE(pl.delivery_terms, '') AS delivery_terms,
                    COALESCE(pl.payment_terms, '') AS payment_terms,
                    COALESCE(pl.estimated_delivery, '') AS estimated_delivery,
                    COALESCE(pl.currency, 'USD') AS currency,
                    COALESCE(pl.notes, '') AS notes,
                    COALESCE(pl.source_type, '') AS source_type,
                    COALESCE(pl.source_number, '') AS source_number,
                    COALESCE(pl.total_pallets, 0) AS total_pallets,
                    COALESCE(pl.total_products, 0) AS total_products,
                    COALESCE(pl.total_quantity, 0) AS total_quantity,
                    COALESCE(pl.total_net_weight, 0) AS total_net_weight,
                    COALESCE(pl.total_gross_weight, 0) AS total_gross_weight,
                    COALESCE(pl.total_volume, 0) AS total_volume,
                    COALESCE(pl.status, 'Draft') AS status,
                    COALESCE(pl.created_by, 'SYSTEM') AS created_by
                FROM packing_lists pl
                LEFT JOIN cariler c ON c.id = pl.customer_id
                WHERE pl.packing_list_number = ?
                LIMIT 1
                """,
                (number,),
            )
            headers = cls._rows_to_dicts(cursor, cursor.fetchall())
            if not headers:
                return None

            header = headers[0]
            cursor.execute(
                """
                SELECT
                    id,
                    pallet_no,
                    COALESCE(pallet_weight, 0) AS pallet_weight,
                    COALESCE(notes, '') AS notes
                FROM packing_list_pallets
                WHERE packing_list_id = ?
                ORDER BY pallet_no
                """,
                (int(header["id"]),),
            )
            header["pallets"] = cls._rows_to_dicts(cursor, cursor.fetchall())

            cursor.execute(
                """
                SELECT
                    pli.id,
                    pli.packing_list_id,
                    pli.pallet_id,
                    COALESCE(pp.pallet_no, '') AS pallet_no,
                    pli.stock_id,
                    COALESCE(pli.stock_code, '') AS stock_code,
                    COALESCE(pli.description, '') AS description,
                    COALESCE(pli.hs_code, '') AS hs_code,
                    COALESCE(pli.quantity, 0) AS quantity,
                    COALESCE(pli.unit, '') AS unit,
                    COALESCE(pli.product_weight, 0) AS product_weight,
                    COALESCE(pli.net_weight, 0) AS net_weight,
                    COALESCE(pli.gross_weight, 0) AS gross_weight,
                    COALESCE(pli.remarks, '') AS remarks,
                    COALESCE(st.brand, '') AS brand,
                    COALESCE(st.unit, pli.unit, '') AS stock_unit
                FROM packing_list_items pli
                LEFT JOIN packing_list_pallets pp ON pp.id = pli.pallet_id
                LEFT JOIN stoklar st ON st.id = pli.stock_id
                WHERE pli.packing_list_id = ?
                ORDER BY pp.pallet_no, pli.id
                """,
                (int(header["id"]),),
            )
            header["items"] = cls._rows_to_dicts(cursor, cursor.fetchall())
            return header

    @classmethod
    def delete_packing_list(cls, packing_list_number: str, *, is_admin: bool = False) -> bool:
        number = str(packing_list_number or "").strip()
        if not number:
            return False

        with cls()._connect() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("BEGIN")
                cursor.execute(
                    "SELECT id, COALESCE(status, 'Draft') FROM packing_lists WHERE packing_list_number = ?",
                    (number,),
                )
                row = cursor.fetchone()
                if row is None:
                    conn.rollback()
                    return False
                packing_list_id = int(row[0])
                status = str(row[1] or "Draft").strip().lower()
                if status not in {"draft", "cancelled"} and not is_admin:
                    conn.rollback()
                    raise ValueError("İşlenmiş belge doğrudan silinemez. Önce iptal edin.")

                cursor.execute("DELETE FROM packing_list_items WHERE packing_list_id = ?", (packing_list_id,))
                cursor.execute("DELETE FROM packing_list_pallets WHERE packing_list_id = ?", (packing_list_id,))
                cursor.execute("DELETE FROM packing_list_history WHERE packing_list_id = ?", (packing_list_id,))
                cursor.execute("DELETE FROM packing_lists WHERE id = ?", (packing_list_id,))
                conn.commit()
                FinanceModel.notify_change("packing-list")
                return True
            except Exception:
                conn.rollback()
                raise

    @classmethod
    def save_packing_list(
        cls,
        header: Dict[str, Any],
        pallets: List[Dict[str, Any]],
        items: List[Dict[str, Any]],
        created_by: str = "SYSTEM",
        existing_packing_list_number: Optional[str] = None,
    ) -> int:
        packing_list_number = str(header.get("packing_list_number") or "").strip()
        if not packing_list_number:
            raise ValueError("Packing List number is required")

        with cls()._connect() as conn:
            cursor = conn.cursor()
            if existing_packing_list_number:
                cursor.execute(
                    "SELECT id FROM packing_lists WHERE packing_list_number = ? AND packing_list_number != ?",
                    (packing_list_number, existing_packing_list_number),
                )
            else:
                cursor.execute("SELECT id FROM packing_lists WHERE packing_list_number = ?", (packing_list_number,))
            if cursor.fetchone() is not None:
                raise ValueError("Packing List number already exists")

        valid_items: List[Dict[str, Any]] = []
        for item in items:
            qty = float(item.get("quantity") or 0)
            stock_id = int(item.get("stock_id") or 0)
            pallet_no = str(item.get("pallet_no") or "").strip()
            if stock_id <= 0 or qty <= 0 or not pallet_no:
                continue
            valid_items.append(dict(item))

        if not valid_items:
            raise ValueError("At least one item is required")

        pallet_map: Dict[str, Dict[str, Any]] = {}
        for pallet in pallets:
            pallet_no = str(pallet.get("pallet_no") or "").strip()
            if not pallet_no:
                continue
            pallet_map[pallet_no] = {
                "pallet_no": pallet_no,
                "pallet_weight": float(pallet.get("pallet_weight") or 0),
                "notes": str(pallet.get("notes") or ""),
            }

        for item in valid_items:
            pallet_no = str(item.get("pallet_no") or "").strip()
            if pallet_no not in pallet_map:
                pallet_map[pallet_no] = {"pallet_no": pallet_no, "pallet_weight": 0.0, "notes": ""}

        total_products = len(valid_items)
        total_quantity = sum(float(item.get("quantity") or 0) for item in valid_items)
        total_net_weight = sum(float(item.get("net_weight") or 0) for item in valid_items)

        total_gross_weight = 0.0
        for pallet_no, pallet in pallet_map.items():
            pallet_net = sum(
                float(item.get("net_weight") or 0)
                for item in valid_items
                if str(item.get("pallet_no") or "").strip() == pallet_no
            )
            total_gross_weight += pallet_net + float(pallet.get("pallet_weight") or 0)

        now_value = cls._now()
        with cls()._connect() as conn:
            cursor = conn.cursor()

            if existing_packing_list_number:
                cursor.execute(
                    "SELECT id FROM packing_lists WHERE packing_list_number = ?",
                    (existing_packing_list_number,),
                )
                row = cursor.fetchone()
                if row is None:
                    raise ValueError("Packing List not found")
                packing_list_id = int(row[0])

                cursor.execute(
                    """
                    UPDATE packing_lists
                    SET
                        packing_list_number = ?,
                        packing_date = ?,
                        customer_id = ?,
                        consignee = ?,
                        notify_party = ?,
                        invoice_number = ?,
                        proforma_number = ?,
                        container_no = ?,
                        seal_no = ?,
                        country = ?,
                        port_of_loading = ?,
                        port_of_discharge = ?,
                        delivery_terms = ?,
                        payment_terms = ?,
                        estimated_delivery = ?,
                        currency = ?,
                        notes = ?,
                        source_type = ?,
                        source_number = ?,
                        total_pallets = ?,
                        total_products = ?,
                        total_quantity = ?,
                        total_net_weight = ?,
                        total_gross_weight = ?,
                        total_volume = ?,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        packing_list_number,
                        str(header.get("packing_date") or ""),
                        int(header.get("customer_id") or 0),
                        str(header.get("consignee") or ""),
                        str(header.get("notify_party") or ""),
                        str(header.get("invoice_number") or ""),
                        str(header.get("proforma_number") or ""),
                        str(header.get("container_no") or ""),
                        str(header.get("seal_no") or ""),
                        str(header.get("country") or ""),
                        str(header.get("port_of_loading") or ""),
                        str(header.get("port_of_discharge") or ""),
                        str(header.get("delivery_terms") or ""),
                        str(header.get("payment_terms") or ""),
                        str(header.get("estimated_delivery") or ""),
                        str(header.get("currency") or "USD") or "USD",
                        str(header.get("notes") or ""),
                        str(header.get("source_type") or ""),
                        str(header.get("source_number") or ""),
                        len(pallet_map),
                        total_products,
                        total_quantity,
                        total_net_weight,
                        total_gross_weight,
                        float(header.get("total_volume") or 0),
                        now_value,
                        packing_list_id,
                    ),
                )
                cursor.execute("DELETE FROM packing_list_items WHERE packing_list_id = ?", (packing_list_id,))
                cursor.execute("DELETE FROM packing_list_pallets WHERE packing_list_id = ?", (packing_list_id,))
                cls._append_history(cursor, packing_list_id, "Updated", "Packing List updated", created_by)
            else:
                cursor.execute(
                    """
                    INSERT INTO packing_lists(
                        packing_list_number,
                        packing_date,
                        customer_id,
                        consignee,
                        notify_party,
                        invoice_number,
                        proforma_number,
                        container_no,
                        seal_no,
                        country,
                        port_of_loading,
                        port_of_discharge,
                        delivery_terms,
                        payment_terms,
                        estimated_delivery,
                        currency,
                        notes,
                        source_type,
                        source_number,
                        total_pallets,
                        total_products,
                        total_quantity,
                        total_net_weight,
                        total_gross_weight,
                        total_volume,
                        status,
                        created_by,
                        created_at,
                        updated_at
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        packing_list_number,
                        str(header.get("packing_date") or ""),
                        int(header.get("customer_id") or 0),
                        str(header.get("consignee") or ""),
                        str(header.get("notify_party") or ""),
                        str(header.get("invoice_number") or ""),
                        str(header.get("proforma_number") or ""),
                        str(header.get("container_no") or ""),
                        str(header.get("seal_no") or ""),
                        str(header.get("country") or ""),
                        str(header.get("port_of_loading") or ""),
                        str(header.get("port_of_discharge") or ""),
                        str(header.get("delivery_terms") or ""),
                        str(header.get("payment_terms") or ""),
                        str(header.get("estimated_delivery") or ""),
                        str(header.get("currency") or "USD") or "USD",
                        str(header.get("notes") or ""),
                        str(header.get("source_type") or ""),
                        str(header.get("source_number") or ""),
                        len(pallet_map),
                        total_products,
                        total_quantity,
                        total_net_weight,
                        total_gross_weight,
                        float(header.get("total_volume") or 0),
                        "Draft",
                        created_by or "SYSTEM",
                        now_value,
                        now_value,
                    ),
                )
                packing_list_id = int(cursor.lastrowid)
                cls._append_history(cursor, packing_list_id, "Created", "Packing List created", created_by)

            pallet_id_by_no: Dict[str, int] = {}
            for pallet_no in sorted(pallet_map.keys()):
                pallet = pallet_map[pallet_no]
                cursor.execute(
                    """
                    INSERT INTO packing_list_pallets(
                        packing_list_id,
                        pallet_no,
                        pallet_weight,
                        notes,
                        created_at,
                        updated_at
                    ) VALUES(?,?,?,?,?,?)
                    """,
                    (
                        packing_list_id,
                        pallet_no,
                        float(pallet.get("pallet_weight") or 0),
                        str(pallet.get("notes") or ""),
                        now_value,
                        now_value,
                    ),
                )
                pallet_id_by_no[pallet_no] = int(cursor.lastrowid)

            for item in valid_items:
                pallet_no = str(item.get("pallet_no") or "").strip()
                pallet_id = pallet_id_by_no.get(pallet_no)
                if pallet_id is None:
                    continue
                cursor.execute(
                    """
                    INSERT INTO packing_list_items(
                        packing_list_id,
                        pallet_id,
                        stock_id,
                        stock_code,
                        description,
                        hs_code,
                        quantity,
                        unit,
                        product_weight,
                        net_weight,
                        gross_weight,
                        remarks,
                        created_at,
                        updated_at
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        packing_list_id,
                        pallet_id,
                        int(item.get("stock_id") or 0),
                        str(item.get("stock_code") or ""),
                        str(item.get("description") or ""),
                        str(item.get("hs_code") or ""),
                        float(item.get("quantity") or 0),
                        str(item.get("unit") or ""),
                        float(item.get("product_weight") or 0),
                        float(item.get("net_weight") or 0),
                        float(item.get("gross_weight") or 0),
                        str(item.get("remarks") or ""),
                        now_value,
                        now_value,
                    ),
                )

            conn.commit()
            FinanceModel.notify_change("packing-list")
            return packing_list_id
