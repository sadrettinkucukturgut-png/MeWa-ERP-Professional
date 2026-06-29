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

    if "hs_code" not in columns:
        cursor.execute("ALTER TABLE stoklar ADD COLUMN hs_code TEXT")

    if "weight" not in columns:
        cursor.execute("ALTER TABLE stoklar ADD COLUMN weight REAL DEFAULT 0")


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


def _ensure_purchase_tables(cursor):
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS purchase_orders(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_number TEXT UNIQUE NOT NULL,
        supplier_id INTEGER NOT NULL,
        order_date TEXT NOT NULL,
        delivery_date TEXT,
        currency TEXT DEFAULT 'USD',
        exchange_rate REAL DEFAULT 1,
        status TEXT DEFAULT 'Draft',
        notes TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (supplier_id) REFERENCES suppliers(id) ON UPDATE CASCADE ON DELETE RESTRICT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS purchase_order_items(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER NOT NULL,
        stock_id INTEGER NOT NULL,
        quantity REAL NOT NULL DEFAULT 0,
        unit TEXT,
        unit_price REAL NOT NULL DEFAULT 0,
        currency TEXT DEFAULT 'USD',
        exchange_rate REAL DEFAULT 1,
        discount_percent REAL DEFAULT 0,
        vat_percent REAL DEFAULT 0,
        line_total REAL NOT NULL DEFAULT 0,
        FOREIGN KEY (order_id) REFERENCES purchase_orders(id) ON UPDATE CASCADE ON DELETE CASCADE,
        FOREIGN KEY (stock_id) REFERENCES stoklar(id) ON UPDATE CASCADE ON DELETE RESTRICT
    )
    """)

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_purchase_orders_supplier_id ON purchase_orders(supplier_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_purchase_orders_order_date ON purchase_orders(order_date)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_purchase_orders_status ON purchase_orders(status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_purchase_order_items_order_id ON purchase_order_items(order_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_purchase_order_items_stock_id ON purchase_order_items(stock_id)")


def _ensure_goods_receipt_tables(cursor):
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS goods_receipts(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        receipt_number TEXT UNIQUE NOT NULL,
        purchase_order_id INTEGER NOT NULL,
        supplier_id INTEGER NOT NULL,
        warehouse TEXT,
        receipt_date TEXT NOT NULL,
        status TEXT DEFAULT 'Posted',
        notes TEXT,
        created_by TEXT DEFAULT 'SYSTEM',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (purchase_order_id) REFERENCES purchase_orders(id) ON UPDATE CASCADE ON DELETE RESTRICT,
        FOREIGN KEY (supplier_id) REFERENCES suppliers(id) ON UPDATE CASCADE ON DELETE RESTRICT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS goods_receipt_items(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        receipt_id INTEGER NOT NULL,
        purchase_order_item_id INTEGER NOT NULL,
        stock_id INTEGER NOT NULL,
        ordered_qty REAL NOT NULL DEFAULT 0,
        received_qty REAL NOT NULL DEFAULT 0,
        remaining_qty REAL NOT NULL DEFAULT 0,
        unit TEXT,
        warehouse TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (receipt_id) REFERENCES goods_receipts(id) ON UPDATE CASCADE ON DELETE CASCADE,
        FOREIGN KEY (purchase_order_item_id) REFERENCES purchase_order_items(id) ON UPDATE CASCADE ON DELETE RESTRICT,
        FOREIGN KEY (stock_id) REFERENCES stoklar(id) ON UPDATE CASCADE ON DELETE RESTRICT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS stock_movements(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        stock_id INTEGER NOT NULL,
        movement_type TEXT NOT NULL,
        quantity REAL NOT NULL,
        reference_type TEXT,
        reference_no TEXT,
        movement_date TEXT NOT NULL,
        warehouse TEXT,
        notes TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (stock_id) REFERENCES stoklar(id) ON UPDATE CASCADE ON DELETE RESTRICT
    )
    """)

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_goods_receipts_po_id ON goods_receipts(purchase_order_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_goods_receipts_supplier_id ON goods_receipts(supplier_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_goods_receipts_receipt_date ON goods_receipts(receipt_date)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_goods_receipts_status ON goods_receipts(status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_goods_receipt_items_receipt_id ON goods_receipt_items(receipt_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_goods_receipt_items_po_item_id ON goods_receipt_items(purchase_order_item_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_goods_receipt_items_stock_id ON goods_receipt_items(stock_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_stock_movements_stock_id ON stock_movements(stock_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_stock_movements_reference_no ON stock_movements(reference_no)")


def _ensure_purchase_invoice_tables(cursor):
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS purchase_invoices(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_number TEXT UNIQUE NOT NULL,
            supplier_id INTEGER NOT NULL,
            purchase_order_id INTEGER,
            goods_receipt_id INTEGER NOT NULL,
            invoice_date TEXT NOT NULL,
            due_date TEXT,
            currency TEXT DEFAULT 'USD',
            exchange_rate REAL DEFAULT 1,
            subtotal REAL NOT NULL DEFAULT 0,
            discount_total REAL NOT NULL DEFAULT 0,
            vat_total REAL NOT NULL DEFAULT 0,
            grand_total REAL NOT NULL DEFAULT 0,
            status TEXT DEFAULT 'Posted',
            notes TEXT,
            created_by TEXT DEFAULT 'SYSTEM',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (supplier_id) REFERENCES suppliers(id) ON UPDATE CASCADE ON DELETE RESTRICT,
            FOREIGN KEY (purchase_order_id) REFERENCES purchase_orders(id) ON UPDATE CASCADE ON DELETE RESTRICT,
            FOREIGN KEY (goods_receipt_id) REFERENCES goods_receipts(id) ON UPDATE CASCADE ON DELETE RESTRICT
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS purchase_invoice_items(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_id INTEGER NOT NULL,
            goods_receipt_item_id INTEGER NOT NULL,
            stock_id INTEGER NOT NULL,
            quantity REAL NOT NULL DEFAULT 0,
            unit TEXT,
            unit_price REAL NOT NULL DEFAULT 0,
            discount_percent REAL NOT NULL DEFAULT 0,
            vat_percent REAL NOT NULL DEFAULT 0,
            line_total REAL NOT NULL DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (invoice_id) REFERENCES purchase_invoices(id) ON UPDATE CASCADE ON DELETE CASCADE,
            FOREIGN KEY (goods_receipt_item_id) REFERENCES goods_receipt_items(id) ON UPDATE CASCADE ON DELETE RESTRICT,
            FOREIGN KEY (stock_id) REFERENCES stoklar(id) ON UPDATE CASCADE ON DELETE RESTRICT
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS supplier_account_movements(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            supplier_id INTEGER NOT NULL,
            movement_date TEXT NOT NULL,
            movement_type TEXT NOT NULL,
            reference_type TEXT,
            reference_no TEXT,
            amount REAL NOT NULL DEFAULT 0,
            currency TEXT DEFAULT 'USD',
            exchange_rate REAL DEFAULT 1,
            description TEXT,
            status TEXT DEFAULT 'Posted',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (supplier_id) REFERENCES suppliers(id) ON UPDATE CASCADE ON DELETE RESTRICT
        )
        """
    )

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_purchase_invoices_supplier_id ON purchase_invoices(supplier_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_purchase_invoices_gr_id ON purchase_invoices(goods_receipt_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_purchase_invoices_invoice_date ON purchase_invoices(invoice_date)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_purchase_invoices_status ON purchase_invoices(status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_purchase_invoice_items_invoice_id ON purchase_invoice_items(invoice_id)")
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_purchase_invoice_items_gr_item_id ON purchase_invoice_items(goods_receipt_item_id)"
    )
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_supplier_movements_supplier_id ON supplier_account_movements(supplier_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_supplier_movements_ref_no ON supplier_account_movements(reference_no)")


def _ensure_sales_invoice_tables(cursor):
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS sales_invoices(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_number TEXT UNIQUE NOT NULL,
            customer_id INTEGER NOT NULL,
            invoice_date TEXT NOT NULL,
            due_date TEXT,
            currency TEXT DEFAULT 'USD',
            exchange_rate REAL DEFAULT 1,
            subtotal REAL NOT NULL DEFAULT 0,
            discount_total REAL NOT NULL DEFAULT 0,
            vat_total REAL NOT NULL DEFAULT 0,
            grand_total REAL NOT NULL DEFAULT 0,
            status TEXT DEFAULT 'Posted',
            notes TEXT,
            created_by TEXT DEFAULT 'SYSTEM',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (customer_id) REFERENCES cariler(id) ON UPDATE CASCADE ON DELETE RESTRICT
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS sales_invoice_items(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_id INTEGER NOT NULL,
            stock_id INTEGER NOT NULL,
            quantity REAL NOT NULL DEFAULT 0,
            unit TEXT,
            unit_price REAL NOT NULL DEFAULT 0,
            discount_percent REAL NOT NULL DEFAULT 0,
            vat_percent REAL NOT NULL DEFAULT 0,
            line_total REAL NOT NULL DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (invoice_id) REFERENCES sales_invoices(id) ON UPDATE CASCADE ON DELETE CASCADE,
            FOREIGN KEY (stock_id) REFERENCES stoklar(id) ON UPDATE CASCADE ON DELETE RESTRICT
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS customer_account_movements(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            movement_date TEXT NOT NULL,
            movement_type TEXT NOT NULL,
            reference_type TEXT,
            reference_no TEXT,
            amount REAL NOT NULL DEFAULT 0,
            currency TEXT DEFAULT 'USD',
            exchange_rate REAL DEFAULT 1,
            description TEXT,
            status TEXT DEFAULT 'Posted',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (customer_id) REFERENCES cariler(id) ON UPDATE CASCADE ON DELETE RESTRICT
        )
        """
    )

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sales_invoices_customer_id ON sales_invoices(customer_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sales_invoices_invoice_date ON sales_invoices(invoice_date)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sales_invoices_status ON sales_invoices(status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sales_invoice_items_invoice_id ON sales_invoice_items(invoice_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sales_invoice_items_stock_id ON sales_invoice_items(stock_id)")
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_customer_movements_customer_id ON customer_account_movements(customer_id)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_customer_movements_ref_no ON customer_account_movements(reference_no)"
    )

    cursor.execute("PRAGMA table_info(sales_invoices)")
    sales_columns = {str(row[1]).lower() for row in cursor.fetchall()}
    if "source_proforma_number" not in sales_columns:
        cursor.execute("ALTER TABLE sales_invoices ADD COLUMN source_proforma_number TEXT")
    if "payment_terms" not in sales_columns:
        cursor.execute("ALTER TABLE sales_invoices ADD COLUMN payment_terms TEXT")
    if "delivery_terms" not in sales_columns:
        cursor.execute("ALTER TABLE sales_invoices ADD COLUMN delivery_terms TEXT")

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sales_invoices_source_pf ON sales_invoices(source_proforma_number)")


def _ensure_proforma_tables(cursor):
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS proforma_headers(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            proforma_number TEXT UNIQUE NOT NULL,
            customer_id INTEGER NOT NULL,
            issue_date TEXT NOT NULL,
            expiry_date TEXT,
            currency TEXT DEFAULT 'USD',
            exchange_rate REAL DEFAULT 1,
            subtotal REAL NOT NULL DEFAULT 0,
            discount_total REAL NOT NULL DEFAULT 0,
            vat_total REAL NOT NULL DEFAULT 0,
            grand_total REAL NOT NULL DEFAULT 0,
            status TEXT DEFAULT 'Draft',
            notes TEXT,
            created_by TEXT DEFAULT 'SYSTEM',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (customer_id) REFERENCES cariler(id) ON UPDATE CASCADE ON DELETE RESTRICT
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS proforma_lines(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            proforma_id INTEGER NOT NULL,
            stock_id INTEGER NOT NULL,
            quantity REAL NOT NULL DEFAULT 0,
            unit TEXT,
            unit_price REAL NOT NULL DEFAULT 0,
            discount_percent REAL NOT NULL DEFAULT 0,
            vat_percent REAL NOT NULL DEFAULT 0,
            line_total REAL NOT NULL DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (proforma_id) REFERENCES proforma_headers(id) ON UPDATE CASCADE ON DELETE CASCADE,
            FOREIGN KEY (stock_id) REFERENCES stoklar(id) ON UPDATE CASCADE ON DELETE RESTRICT
        )
        """
    )

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_proforma_headers_customer_id ON proforma_headers(customer_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_proforma_headers_issue_date ON proforma_headers(issue_date)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_proforma_headers_status ON proforma_headers(status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_proforma_lines_proforma_id ON proforma_lines(proforma_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_proforma_lines_stock_id ON proforma_lines(stock_id)")

    cursor.execute("PRAGMA table_info(proforma_headers)")
    proforma_columns = {str(row[1]).lower() for row in cursor.fetchall()}
    if "payment_terms" not in proforma_columns:
        cursor.execute("ALTER TABLE proforma_headers ADD COLUMN payment_terms TEXT")
    if "delivery_terms" not in proforma_columns:
        cursor.execute("ALTER TABLE proforma_headers ADD COLUMN delivery_terms TEXT")
    if "converted_invoice_number" not in proforma_columns:
        cursor.execute("ALTER TABLE proforma_headers ADD COLUMN converted_invoice_number TEXT")
    if "converted_at" not in proforma_columns:
        cursor.execute("ALTER TABLE proforma_headers ADD COLUMN converted_at DATETIME")

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS proforma_history(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            proforma_id INTEGER NOT NULL,
            event_type TEXT NOT NULL,
            event_note TEXT,
            created_by TEXT DEFAULT 'SYSTEM',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (proforma_id) REFERENCES proforma_headers(id) ON UPDATE CASCADE ON DELETE CASCADE
        )
        """
    )
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_proforma_history_proforma_id ON proforma_history(proforma_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_proforma_headers_converted_invoice ON proforma_headers(converted_invoice_number)")


def _ensure_packing_list_tables(cursor):
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS packing_lists(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            packing_list_number TEXT UNIQUE NOT NULL,
            packing_date TEXT NOT NULL,
            customer_id INTEGER NOT NULL,
            consignee TEXT,
            notify_party TEXT,
            invoice_number TEXT,
            proforma_number TEXT,
            container_no TEXT,
            seal_no TEXT,
            country TEXT,
            port_of_loading TEXT,
            port_of_discharge TEXT,
            delivery_terms TEXT,
            payment_terms TEXT,
            estimated_delivery TEXT,
            currency TEXT DEFAULT 'USD',
            notes TEXT,
            source_type TEXT NOT NULL,
            source_number TEXT NOT NULL,
            total_pallets INTEGER DEFAULT 0,
            total_products INTEGER DEFAULT 0,
            total_quantity REAL DEFAULT 0,
            total_net_weight REAL DEFAULT 0,
            total_gross_weight REAL DEFAULT 0,
            total_volume REAL DEFAULT 0,
            status TEXT DEFAULT 'Draft',
            created_by TEXT DEFAULT 'SYSTEM',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (customer_id) REFERENCES cariler(id) ON UPDATE CASCADE ON DELETE RESTRICT
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS packing_list_pallets(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            packing_list_id INTEGER NOT NULL,
            pallet_no TEXT NOT NULL,
            pallet_weight REAL DEFAULT 0,
            notes TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (packing_list_id) REFERENCES packing_lists(id) ON UPDATE CASCADE ON DELETE CASCADE,
            UNIQUE(packing_list_id, pallet_no)
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS packing_list_items(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            packing_list_id INTEGER NOT NULL,
            pallet_id INTEGER NOT NULL,
            stock_id INTEGER NOT NULL,
            stock_code TEXT,
            description TEXT,
            hs_code TEXT,
            quantity REAL DEFAULT 0,
            unit TEXT,
            product_weight REAL DEFAULT 0,
            net_weight REAL DEFAULT 0,
            gross_weight REAL DEFAULT 0,
            remarks TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (packing_list_id) REFERENCES packing_lists(id) ON UPDATE CASCADE ON DELETE CASCADE,
            FOREIGN KEY (pallet_id) REFERENCES packing_list_pallets(id) ON UPDATE CASCADE ON DELETE CASCADE,
            FOREIGN KEY (stock_id) REFERENCES stoklar(id) ON UPDATE CASCADE ON DELETE RESTRICT
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS packing_list_history(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            packing_list_id INTEGER NOT NULL,
            event_type TEXT NOT NULL,
            event_note TEXT,
            created_by TEXT DEFAULT 'SYSTEM',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (packing_list_id) REFERENCES packing_lists(id) ON UPDATE CASCADE ON DELETE CASCADE
        )
        """
    )

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_packing_lists_number ON packing_lists(packing_list_number)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_packing_lists_date ON packing_lists(packing_date)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_packing_lists_source ON packing_lists(source_type, source_number)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_packing_list_pallets_list_id ON packing_list_pallets(packing_list_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_packing_list_items_list_id ON packing_list_items(packing_list_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_packing_list_items_pallet_id ON packing_list_items(pallet_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_packing_list_items_stock_id ON packing_list_items(stock_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_packing_list_history_list_id ON packing_list_history(packing_list_id)")


def create_database():

    conn = sqlite3.connect("database/mewa.db")
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON")

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
        hs_code TEXT,
        weight REAL DEFAULT 0,
        current_stock REAL DEFAULT 0,
        shelf TEXT,
        origin TEXT,
        description TEXT,
        image_path TEXT,

        created_at DATETIME DEFAULT CURRENT_TIMESTAMP

    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS suppliers(

        id INTEGER PRIMARY KEY AUTOINCREMENT,

        supplier_code TEXT UNIQUE NOT NULL,
        company_name TEXT NOT NULL,
        contact_person TEXT NOT NULL,
        phone TEXT,
        whatsapp TEXT,
        email TEXT,
        website TEXT,
        tax_office TEXT,
        tax_number TEXT,
        country TEXT,
        city TEXT,
        district TEXT,
        address TEXT,
        default_currency TEXT DEFAULT 'USD',
        payment_term TEXT,
        bank_name TEXT,
        iban TEXT,
        swift_code TEXT,
        notes TEXT,

        created_at DATETIME DEFAULT CURRENT_TIMESTAMP

    )
    """)

    _ensure_stock_currency_columns(cursor)
    _ensure_stock_reference_tables(cursor)
    _ensure_purchase_tables(cursor)
    _ensure_goods_receipt_tables(cursor)
    _ensure_purchase_invoice_tables(cursor)
    _ensure_sales_invoice_tables(cursor)
    _ensure_proforma_tables(cursor)
    _ensure_packing_list_tables(cursor)

    conn.commit()
    conn.close()