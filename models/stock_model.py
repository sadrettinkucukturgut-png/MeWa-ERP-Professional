# ==========================================
# MeWa ERP Professional
# File : stock_model.py
# Version : 0.1
# ==========================================

from datetime import datetime
import sqlite3


class StockModel:

    DB_PATH = "database/mewa.db"

    @classmethod
    def ekle(
        cls,
        stock_code,
        barcode,
        product_name,
        category,
        hs_code,
        brand,
        unit,
        purchase_price,
        purchase_currency,
        sale_price,
        sale_currency,
        vat_rate,
        weight,
        current_stock,
        shelf,
        origin,
        description,
        image_path=None,
    ):

        with sqlite3.connect(cls.DB_PATH) as conn:
            cursor = conn.cursor()

            cursor.execute("""

            INSERT INTO stoklar(

                stock_code,
                barcode,
                product_name,
                category,
                hs_code,
                brand,
                unit,
                purchase_price,
                purchase_currency,
                sale_price,
                sale_currency,
                vat_rate,
                weight,
                current_stock,
                shelf,
                origin,
                description,
                image_path

            )

            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)

            """, (

                stock_code,
                barcode,
                product_name,
                category,
                hs_code,
                brand,
                unit,
                purchase_price,
                purchase_currency or "USD",
                sale_price,
                sale_currency or "USD",
                vat_rate,
                weight,
                current_stock,
                shelf,
                origin,
                description,
                image_path,

            ))

            stock_id = int(cursor.lastrowid or 0)
            initial_stock = float(current_stock or 0)
            if stock_id > 0 and initial_stock != 0:
                movement_type = "ManualStockEntry" if initial_stock > 0 else "ManualStockExit"
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
                        movement_type,
                        abs(initial_stock),
                        "StockCard",
                        stock_code,
                        datetime.now().strftime("%Y-%m-%d"),
                        "",
                        "Manual opening stock from stock card",
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    ),
                )

            conn.commit()

    @classmethod
    def tum_stoklar(cls):

        with sqlite3.connect(cls.DB_PATH) as conn:
            cursor = conn.cursor()

            cursor.execute("""

            SELECT

                stock_code,
                barcode,
                product_name,
                category,
                hs_code,
                brand,
                unit,
                purchase_price,
                purchase_currency,
                sale_price,
                sale_currency,
                vat_rate,
                weight,
                current_stock,
                shelf,
                origin,
                description,
                image_path

            FROM stoklar

            ORDER BY product_name

            """)

            return cursor.fetchall()

    @classmethod
    def getir(cls, stock_code):

        with sqlite3.connect(cls.DB_PATH) as conn:
            cursor = conn.cursor()

            cursor.execute("""

            SELECT

                stock_code,
                barcode,
                product_name,
                category,
                hs_code,
                brand,
                unit,
                purchase_price,
                purchase_currency,
                sale_price,
                sale_currency,
                vat_rate,
                weight,
                current_stock,
                shelf,
                origin,
                description,
                image_path

            FROM stoklar

            WHERE stock_code = ?

            """, (stock_code,))

            return cursor.fetchone()

    @classmethod
    def guncelle(
        cls,
        stock_code,
        barcode,
        product_name,
        category,
        hs_code,
        brand,
        unit,
        purchase_price,
        purchase_currency,
        sale_price,
        sale_currency,
        vat_rate,
        weight,
        current_stock,
        shelf,
        origin,
        description,
        image_path=None,
    ):

        with sqlite3.connect(cls.DB_PATH) as conn:
            cursor = conn.cursor()

            cursor.execute(
                "SELECT id, COALESCE(current_stock, 0) FROM stoklar WHERE stock_code = ?",
                (stock_code,),
            )
            existing = cursor.fetchone()
            existing_stock = float(existing[1] if existing else 0)
            stock_id = int(existing[0] if existing else 0)

            cursor.execute("""

            UPDATE stoklar

            SET

                barcode = ?,
                product_name = ?,
                category = ?,
                hs_code = ?,
                brand = ?,
                unit = ?,
                purchase_price = ?,
                purchase_currency = ?,
                sale_price = ?,
                sale_currency = ?,
                vat_rate = ?,
                weight = ?,
                current_stock = ?,
                shelf = ?,
                origin = ?,
                description = ?,
                image_path = ?

            WHERE stock_code = ?

            """, (

                barcode,
                product_name,
                category,
                hs_code,
                brand,
                unit,
                purchase_price,
                purchase_currency or "USD",
                sale_price,
                sale_currency or "USD",
                vat_rate,
                weight,
                current_stock,
                shelf,
                origin,
                description,
                image_path,
                stock_code,

            ))

            new_stock = float(current_stock or 0)
            delta = new_stock - existing_stock
            if stock_id > 0 and abs(delta) > 1e-9:
                movement_type = "ManualStockEntry" if delta > 0 else "ManualStockExit"
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
                        movement_type,
                        abs(delta),
                        "StockCard",
                        stock_code,
                        datetime.now().strftime("%Y-%m-%d"),
                        "",
                        "Manual stock adjustment from stock card",
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    ),
                )

            conn.commit()

    @classmethod
    def sil(cls, stock_code):

        with sqlite3.connect(cls.DB_PATH) as conn:
            cursor = conn.cursor()

            cursor.execute("""

            DELETE FROM stoklar

            WHERE stock_code = ?

            """, (stock_code,))

            conn.commit()

    @classmethod
    def barcode_exists(cls, barcode, exclude_stock_code=None):
        if not barcode:
            return False

        with sqlite3.connect(cls.DB_PATH) as conn:
            cursor = conn.cursor()
            if exclude_stock_code:
                cursor.execute(
                    "SELECT 1 FROM stoklar WHERE LOWER(barcode) = LOWER(?) AND stock_code != ?",
                    (barcode, exclude_stock_code),
                )
            else:
                cursor.execute(
                    "SELECT 1 FROM stoklar WHERE LOWER(barcode) = LOWER(?)",
                    (barcode,),
                )
            return cursor.fetchone() is not None

    @classmethod
    def get_categories(cls):
        with sqlite3.connect(cls.DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM stok_kategoriler ORDER BY name")
            return [row[0] for row in cursor.fetchall()]

    @classmethod
    def add_category(cls, name):
        with sqlite3.connect(cls.DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT OR IGNORE INTO stok_kategoriler(name) VALUES(?)", (name,))
            conn.commit()

    @classmethod
    def get_warehouses(cls):
        with sqlite3.connect(cls.DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM stok_depolar ORDER BY name")
            return [row[0] for row in cursor.fetchall()]

    @classmethod
    def add_warehouse(cls, name):
        with sqlite3.connect(cls.DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT OR IGNORE INTO stok_depolar(name) VALUES(?)", (name,))
            conn.commit()

    @classmethod
    def get_brands(cls):
        with sqlite3.connect(cls.DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM stok_markalar ORDER BY name")
            return [row[0] for row in cursor.fetchall()]

    @classmethod
    def add_brand(cls, name):
        with sqlite3.connect(cls.DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT OR IGNORE INTO stok_markalar(name) VALUES(?)", (name,))
            conn.commit()

    @classmethod
    def get_stock_by_id(cls, stock_id):
        with sqlite3.connect(cls.DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT
                    id,
                    stock_code,
                    product_name,
                    category,
                    hs_code,
                    brand,
                    unit,
                    weight,
                    current_stock
                FROM stoklar
                WHERE id = ?
                """,
                (stock_id,),
            )
            row = cursor.fetchone()
            return dict(row) if row is not None else None

    @classmethod
    def resolve_supplier_for_stock(cls, stock_id: int) -> dict:
        if int(stock_id or 0) <= 0:
            return {}

        with sqlite3.connect(cls.DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Prefer most recent posted purchase invoice for this stock.
            cursor.execute(
                """
                SELECT
                    s.id AS supplier_id,
                    COALESCE(s.company_name, '') AS company_name,
                    COALESCE(s.whatsapp, '') AS whatsapp,
                    COALESCE(s.phone, '') AS phone
                FROM purchase_invoice_items pii
                INNER JOIN purchase_invoices pi ON pi.id = pii.invoice_id
                INNER JOIN suppliers s ON s.id = pi.supplier_id
                WHERE pii.stock_id = ?
                  AND LOWER(COALESCE(pi.status, '')) != 'cancelled'
                ORDER BY DATE(COALESCE(pi.invoice_date, '')) DESC, pi.id DESC
                LIMIT 1
                """,
                (stock_id,),
            )
            row = cursor.fetchone()
            if row is None:
                cursor.execute(
                    """
                    SELECT
                        s.id AS supplier_id,
                        COALESCE(s.company_name, '') AS company_name,
                        COALESCE(s.whatsapp, '') AS whatsapp,
                        COALESCE(s.phone, '') AS phone
                    FROM purchase_order_items poi
                    INNER JOIN purchase_orders po ON po.id = poi.order_id
                    INNER JOIN suppliers s ON s.id = po.supplier_id
                    WHERE poi.stock_id = ?
                      AND LOWER(COALESCE(po.status, '')) != 'cancelled'
                    ORDER BY DATE(COALESCE(po.order_date, '')) DESC, po.id DESC
                    LIMIT 1
                    """,
                    (stock_id,),
                )
                row = cursor.fetchone()

            return dict(row) if row is not None else {}

    @classmethod
    def _table_exists(cls, cursor, table_name: str) -> bool:
        cursor.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND LOWER(name) = LOWER(?)",
            (table_name,),
        )
        return cursor.fetchone() is not None

    @classmethod
    def _ensure_purchase_invoice_movements(cls, cursor) -> int:
        if not cls._table_exists(cursor, "purchase_invoices") or not cls._table_exists(cursor, "purchase_invoice_items"):
            return 0

        cursor.execute(
            """
            SELECT
                pii.id AS line_id,
                pii.stock_id,
                COALESCE(pii.quantity, 0) AS quantity,
                COALESCE(pi.invoice_number, '') AS invoice_number,
                COALESCE(pi.invoice_date, '') AS invoice_date,
                COALESCE(gri.warehouse, '') AS warehouse,
                COALESCE(pi.created_at, CURRENT_TIMESTAMP) AS created_at
            FROM purchase_invoice_items pii
            INNER JOIN purchase_invoices pi ON pi.id = pii.invoice_id
            LEFT JOIN goods_receipt_items gri ON gri.id = pii.goods_receipt_item_id
            WHERE LOWER(COALESCE(pi.status, '')) != 'cancelled'
            ORDER BY pi.id ASC, pii.id ASC
            """
        )
        rows = cursor.fetchall()

        inserted = 0
        for line_id, stock_id, quantity, invoice_number, invoice_date, warehouse, created_at in rows:
            sid = int(stock_id or 0)
            qty = abs(float(quantity or 0))
            inv_no = str(invoice_number or "").strip()
            inv_date = str(invoice_date or "").strip()
            if sid <= 0 or qty <= 0 or not inv_no:
                continue

            notes = f"Purchase Invoice {inv_no} Line {int(line_id or 0)}"
            cursor.execute(
                """
                SELECT 1
                FROM stock_movements
                WHERE stock_id = ?
                  AND LOWER(COALESCE(movement_type, '')) IN ('purchase', 'purchaseinvoice')
                  AND LOWER(COALESCE(reference_type, '')) = 'purchaseinvoice'
                  AND COALESCE(reference_no, '') = ?
                  AND COALESCE(notes, '') = ?
                LIMIT 1
                """,
                (sid, inv_no, notes),
            )
            if cursor.fetchone() is not None:
                continue

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
                    sid,
                    "PURCHASE",
                    qty,
                    "PurchaseInvoice",
                    inv_no,
                    inv_date,
                    warehouse,
                    notes,
                    created_at,
                ),
            )
            inserted += 1
        return inserted

    @classmethod
    def _ensure_sales_invoice_movements(cls, cursor) -> int:
        # Optional compatibility path: only runs if a sales invoice schema exists.
        if not cls._table_exists(cursor, "sales_invoices") or not cls._table_exists(cursor, "sales_invoice_items"):
            return 0

        cursor.execute("PRAGMA table_info(sales_invoices)")
        invoice_cols = {str(row[1]).lower() for row in cursor.fetchall()}
        cursor.execute("PRAGMA table_info(sales_invoice_items)")
        item_cols = {str(row[1]).lower() for row in cursor.fetchall()}

        if "id" not in invoice_cols:
            return 0
        if "invoice_id" not in item_cols or "stock_id" not in item_cols:
            return 0

        no_col = "invoice_number" if "invoice_number" in invoice_cols else ("invoice_no" if "invoice_no" in invoice_cols else "id")
        date_col = "invoice_date" if "invoice_date" in invoice_cols else ("date" if "date" in invoice_cols else "created_at")
        status_col = "status" if "status" in invoice_cols else None
        qty_col = "quantity" if "quantity" in item_cols else ("qty" if "qty" in item_cols else None)
        if qty_col is None:
            return 0

        status_filter = ""
        if status_col:
            status_filter = f"WHERE LOWER(COALESCE(si.{status_col}, '')) != 'cancelled'"

        cursor.execute(
            f"""
            SELECT
                sii.id AS line_id,
                sii.stock_id,
                COALESCE(sii.{qty_col}, 0) AS quantity,
                COALESCE(si.{no_col}, '') AS invoice_no,
                COALESCE(si.{date_col}, '') AS invoice_date,
                COALESCE(si.created_at, CURRENT_TIMESTAMP) AS created_at
            FROM sales_invoice_items sii
            INNER JOIN sales_invoices si ON si.id = sii.invoice_id
            {status_filter}
            ORDER BY si.id ASC, sii.id ASC
            """
        )
        rows = cursor.fetchall()

        inserted = 0
        for line_id, stock_id, quantity, invoice_no, invoice_date, created_at in rows:
            sid = int(stock_id or 0)
            qty = abs(float(quantity or 0))
            inv_no = str(invoice_no or "").strip()
            if sid <= 0 or qty <= 0 or not inv_no:
                continue

            notes = f"Sales Invoice {inv_no} Line {int(line_id or 0)}"
            cursor.execute(
                """
                SELECT 1
                FROM stock_movements
                WHERE stock_id = ?
                  AND LOWER(COALESCE(movement_type, '')) IN ('sale', 'salesinvoice')
                  AND LOWER(COALESCE(reference_type, '')) = 'salesinvoice'
                  AND COALESCE(reference_no, '') = ?
                  AND COALESCE(notes, '') = ?
                LIMIT 1
                """,
                (sid, inv_no, notes),
            )
            if cursor.fetchone() is not None:
                continue

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
                    sid,
                    "SALE",
                    qty,
                    "SalesInvoice",
                    inv_no,
                    str(invoice_date or ""),
                    "",
                    notes,
                    str(created_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                ),
            )
            inserted += 1

        return inserted

    @classmethod
    def _parse_date_value(cls, value: str):
        raw = str(value or "").strip()
        if not raw:
            return None
        for fmt in (
            "%Y-%m-%d",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
            "%d.%m.%Y",
            "%d/%m/%Y",
        ):
            try:
                return datetime.strptime(raw, fmt).date()
            except ValueError:
                continue
        if len(raw) >= 10:
            try:
                return datetime.strptime(raw[:10], "%Y-%m-%d").date()
            except ValueError:
                pass
        return None

    @classmethod
    def stock_movement_ledger(
        cls,
        stock_id: int,
        start_date: str,
        end_date: str,
    ) -> dict:
        stock_id = int(stock_id or 0)
        if stock_id <= 0:
            return {
                "rows": [],
                "opening_stock": 0.0,
                "total_in": 0.0,
                "total_out": 0.0,
                "closing_stock": 0.0,
            }

        with sqlite3.connect(cls.DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            inserted_purchase = cls._ensure_purchase_invoice_movements(cursor)
            inserted_sales = cls._ensure_sales_invoice_movements(cursor)
            if inserted_purchase > 0 or inserted_sales > 0:
                conn.commit()

            sql_stock_only = (
                "SELECT sm.id, sm.movement_date, sm.reference_type, sm.reference_no, sm.movement_type, "
                "sm.warehouse, sm.quantity, sm.notes, sm.created_at, st.unit, st.hs_code, st.weight "
                "FROM stock_movements sm LEFT JOIN stoklar st ON st.id = sm.stock_id "
                "WHERE sm.stock_id = ? ORDER BY sm.id ASC"
            )
            cursor.execute(
                """
                SELECT
                    sm.id,
                    COALESCE(sm.movement_date, '') AS movement_date,
                    COALESCE(sm.reference_type, '') AS reference_type,
                    COALESCE(sm.reference_no, '') AS reference_no,
                    COALESCE(sm.movement_type, '') AS movement_type,
                    COALESCE(sm.warehouse, '') AS warehouse,
                    COALESCE(sm.quantity, 0) AS quantity,
                    COALESCE(sm.notes, '') AS notes,
                    COALESCE(sm.created_at, '') AS created_at,
                    COALESCE(st.unit, '') AS unit,
                    COALESCE(st.hs_code, '') AS hs_code,
                    COALESCE(st.weight, 0) AS weight
                FROM stock_movements sm
                LEFT JOIN stoklar st ON st.id = sm.stock_id
                WHERE sm.stock_id = ?
                ORDER BY sm.id ASC
                """,
                (stock_id,),
            )
            all_rows = cursor.fetchall()

        start_date_obj = cls._parse_date_value(start_date)
        end_date_obj = cls._parse_date_value(end_date)

        def in_period(row_date):
            if row_date is None:
                return True
            if start_date_obj is not None and row_date < start_date_obj:
                return False
            if end_date_obj is not None and row_date > end_date_obj:
                return False
            return True

        opening_rows = []
        period_rows = []
        for row in all_rows:
            parsed_date = cls._parse_date_value(str(row["movement_date"] or ""))
            payload = dict(row)
            payload["_parsed_date"] = parsed_date
            if start_date_obj is not None and parsed_date is not None and parsed_date < start_date_obj:
                opening_rows.append(payload)
                continue
            if in_period(parsed_date):
                period_rows.append(payload)

        period_rows.sort(
            key=lambda item: (
                item.get("_parsed_date") or datetime.min.date(),
                int(item.get("id") or 0),
            )
        )
        opening_rows.sort(
            key=lambda item: (
                item.get("_parsed_date") or datetime.min.date(),
                int(item.get("id") or 0),
            )
        )

        def direction_for(movement_type: str, quantity: float) -> int:
            qty = float(quantity or 0)
            if qty < 0:
                return -1
            outgoing_types = {
                "sale",
                "salesinvoice",
                "salesreturnout",
                "goodsissue",
                "manualstockexit",
                "stockexit",
                "warehousetransferout",
                "productionconsumption",
                "inventorycountdifferenceminus",
                "adjustmentout",
                "stockout",
            }
            incoming_types = {
                "purchase",
                "purchaseinvoice",
                "purchasereturnin",
                "goodsreceipt",
                "manualstockentry",
                "stockentry",
                "warehousetransferin",
                "productionoutput",
                "inventorycountdifferenceplus",
                "adjustmentin",
                "stockin",
            }
            normalized_type = str(movement_type or "").strip().lower()
            if normalized_type in outgoing_types:
                return -1
            if normalized_type in incoming_types:
                return 1
            return 1

        opening_stock = 0.0
        for row in opening_rows:
            qty = float(row["quantity"] or 0)
            direction = direction_for(row["movement_type"], qty)
            opening_stock += abs(qty) * direction

        running_balance = opening_stock
        total_in = 0.0
        total_out = 0.0
        normalized_rows = []

        label_map = {
            "goodsreceipt": "Mal Kabul",
            "goodsissue": "Mal Çıkış",
            "purchase": "Alış",
            "sale": "Satış",
            "purchaseinvoice": "Alış Faturası",
            "salesinvoice": "Satış Faturası",
            "purchasereturnin": "Alış İade",
            "salesreturnout": "Satış İade",
            "manualstockentry": "Manuel Stok Girişi",
            "manualstockexit": "Manuel Stok Çıkışı",
            "warehousetransferin": "Depolar Arası Transfer (Giriş)",
            "warehousetransferout": "Depolar Arası Transfer (Çıkış)",
            "productionconsumption": "Üretim Sarf",
            "productionoutput": "Üretim Çıktısı",
            "inventorycountdifferenceplus": "Sayım Farkı (+)",
            "inventorycountdifferenceminus": "Sayım Farkı (-)",
            "adjustmentin": "Stok Düzeltme (+)",
            "adjustmentout": "Stok Düzeltme (-)",
        }

        document_type_map = {
            "goodsreceipt": "Mal Kabul",
            "purchase": "Alis",
            "sale": "Satis",
            "purchaseinvoice": "Alis Faturasi",
            "salesinvoice": "Satis Faturasi",
            "manualstockentry": "Manuel Stok Girisi",
            "manualstockexit": "Manuel Stok Cikisi",
            "warehousetransferin": "Depo Transfer Giris",
            "warehousetransferout": "Depo Transfer Cikis",
        }

        for row in period_rows:
            movement_type_raw = str(row.get("movement_type") or "")
            movement_type_key = movement_type_raw.strip().lower()
            qty = float(row.get("quantity") or 0)
            abs_qty = abs(qty)
            direction = direction_for(movement_type_key, qty)

            in_qty = abs_qty if direction > 0 else 0.0
            out_qty = abs_qty if direction < 0 else 0.0

            running_balance += in_qty - out_qty
            total_in += in_qty
            total_out += out_qty

            raw_document_type = str(row.get("reference_type") or movement_type_raw or "Belge")
            document_type = document_type_map.get(str(raw_document_type).strip().lower(), raw_document_type)
            document_no = str(row.get("reference_no") or "")
            fallback_description = f"{document_type} {document_no}".strip()
            description = str(row.get("notes") or "").strip() or fallback_description or label_map.get(
                movement_type_key,
                movement_type_raw or "Hareket",
            )

            normalized_rows.append(
                {
                    "date": str(row.get("movement_date") or ""),
                    "document_type": document_type,
                    "document_no": document_no,
                    "movement_type": label_map.get(movement_type_key, movement_type_raw or "Hareket"),
                    "warehouse": str(row.get("warehouse") or ""),
                    "in_qty": in_qty,
                    "out_qty": out_qty,
                    "balance_qty": running_balance,
                    "unit": str(row.get("unit") or ""),
                    "user": "SYSTEM",
                    "description": description,
                    "status": "Posted",
                    "movement_id": int(row.get("id") or 0),
                    "reference_type": str(row.get("reference_type") or ""),
                }
            )

        return {
            "rows": normalized_rows,
            "opening_stock": opening_stock,
            "total_in": total_in,
            "total_out": total_out,
            "closing_stock": opening_stock + total_in - total_out,
            "debug": {
                "selected_stock_id": stock_id,
                "sql": sql_stock_only,
                "stock_only_row_count": len(all_rows),
                "period_row_count": len(period_rows),
                "date_filter_warning": len(all_rows) > 0 and len(period_rows) == 0,
                "backfilled_purchase_rows": inserted_purchase,
                "backfilled_sales_rows": inserted_sales,
            },
        }