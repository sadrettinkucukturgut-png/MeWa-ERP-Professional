# ==========================================
# MeWa ERP Professional
# File : database.py
# Version : 0.3
# ==========================================

import sqlite3


def _ensure_stock_currency_columns(cursor):
    cursor.execute("PRAGMA table_info(stoklar)")
    columns = {row[1] for row in cursor.fetchall()}

    if "purchase_currency" not in columns:
        cursor.execute("ALTER TABLE stoklar ADD COLUMN purchase_currency TEXT DEFAULT 'USD'")

    if "sale_currency" not in columns:
        cursor.execute("ALTER TABLE stoklar ADD COLUMN sale_currency TEXT DEFAULT 'USD'")

    if "image_path" not in columns:
        cursor.execute("ALTER TABLE stoklar ADD COLUMN image_path TEXT")


def _ensure_stock_reference_tables(cursor):
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS stok_kategoriler(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS stok_depolar(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS stok_markalar(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL
    )
    """)

    cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_stoklar_barcode_nonempty ON stoklar(barcode) WHERE barcode IS NOT NULL AND barcode != ''")


def create_database():

    conn = sqlite3.connect("database/mewa.db")
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS cariler(

        id INTEGER PRIMARY KEY AUTOINCREMENT,

        cari_kodu TEXT UNIQUE NOT NULL,
        firma_unvani TEXT NOT NULL,
        yetkili TEXT NOT NULL,

        telefon TEXT,

        email TEXT NOT NULL,

        vergi_dairesi TEXT NOT NULL,
        vergi_no TEXT NOT NULL,

        ulke TEXT NOT NULL,
        sehir TEXT NOT NULL,
        ilce TEXT NOT NULL,

        adres TEXT NOT NULL,

        created_at DATETIME DEFAULT CURRENT_TIMESTAMP

    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS stoklar(

        id INTEGER PRIMARY KEY AUTOINCREMENT,

        stock_code TEXT UNIQUE NOT NULL,
        barcode TEXT,
        product_name TEXT NOT NULL,
        category TEXT,
        brand TEXT,
        unit TEXT,
        purchase_price REAL DEFAULT 0,
        purchase_currency TEXT DEFAULT 'USD',
        sale_price REAL DEFAULT 0,
        sale_currency TEXT DEFAULT 'USD',
        vat_rate REAL DEFAULT 0,
        critical_stock REAL DEFAULT 0,
        current_stock REAL DEFAULT 0,
        warehouse TEXT,
        shelf TEXT,
        origin TEXT,
        description TEXT,
        image_path TEXT,

        created_at DATETIME DEFAULT CURRENT_TIMESTAMP

    )
    """)

    _ensure_stock_currency_columns(cursor)
    _ensure_stock_reference_tables(cursor)

    conn.commit()
    conn.close()