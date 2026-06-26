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
        sale_price,
        vat_rate,
        critical_stock,
        current_stock,
        warehouse,
        shelf,
        origin,
        description
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
                sale_price,
                vat_rate,
                critical_stock,
                current_stock,
                warehouse,
                shelf,
                origin,
                description

            )

            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)

            """, (

                stock_code,
                barcode,
                product_name,
                category,
                brand,
                unit,
                purchase_price,
                sale_price,
                vat_rate,
                critical_stock,
                current_stock,
                warehouse,
                shelf,
                origin,
                description

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
                sale_price,
                vat_rate,
                critical_stock,
                current_stock,
                warehouse,
                shelf,
                origin,
                description

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
                sale_price,
                vat_rate,
                critical_stock,
                current_stock,
                warehouse,
                shelf,
                origin,
                description

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
        sale_price,
        vat_rate,
        critical_stock,
        current_stock,
        warehouse,
        shelf,
        origin,
        description
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
                sale_price = ?,
                vat_rate = ?,
                critical_stock = ?,
                current_stock = ?,
                warehouse = ?,
                shelf = ?,
                origin = ?,
                description = ?

            WHERE stock_code = ?

            """, (

                barcode,
                product_name,
                category,
                brand,
                unit,
                purchase_price,
                sale_price,
                vat_rate,
                critical_stock,
                current_stock,
                warehouse,
                shelf,
                origin,
                description,
                stock_code

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