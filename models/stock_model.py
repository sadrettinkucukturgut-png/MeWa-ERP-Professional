# ==========================================
# MeWa ERP Professional
# File : stock_model.py
# Version : 0.1
# ==========================================

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
        brand,
        unit,
        purchase_price,
        purchase_currency,
        sale_price,
        sale_currency,
        vat_rate,
        critical_stock,
        current_stock,
        warehouse,
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
                brand,
                unit,
                purchase_price,
                purchase_currency,
                sale_price,
                sale_currency,
                vat_rate,
                critical_stock,
                current_stock,
                warehouse,
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
                brand,
                unit,
                purchase_price,
                purchase_currency or "USD",
                sale_price,
                sale_currency or "USD",
                vat_rate,
                critical_stock,
                current_stock,
                warehouse,
                shelf,
                origin,
                description,
                image_path,

            ))

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
                brand,
                unit,
                purchase_price,
                purchase_currency,
                sale_price,
                sale_currency,
                vat_rate,
                critical_stock,
                current_stock,
                warehouse,
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
                brand,
                unit,
                purchase_price,
                purchase_currency,
                sale_price,
                sale_currency,
                vat_rate,
                critical_stock,
                current_stock,
                warehouse,
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
        brand,
        unit,
        purchase_price,
        purchase_currency,
        sale_price,
        sale_currency,
        vat_rate,
        critical_stock,
        current_stock,
        warehouse,
        shelf,
        origin,
        description,
        image_path=None,
    ):

        with sqlite3.connect(cls.DB_PATH) as conn:
            cursor = conn.cursor()

            cursor.execute("""

            UPDATE stoklar

            SET

                barcode = ?,
                product_name = ?,
                category = ?,
                brand = ?,
                unit = ?,
                purchase_price = ?,
                purchase_currency = ?,
                sale_price = ?,
                sale_currency = ?,
                vat_rate = ?,
                critical_stock = ?,
                current_stock = ?,
                warehouse = ?,
                shelf = ?,
                origin = ?,
                description = ?,
                image_path = ?

            WHERE stock_code = ?

            """, (

                barcode,
                product_name,
                category,
                brand,
                unit,
                purchase_price,
                purchase_currency or "USD",
                sale_price,
                sale_currency or "USD",
                vat_rate,
                critical_stock,
                current_stock,
                warehouse,
                shelf,
                origin,
                description,
                image_path,
                stock_code,

            ))

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