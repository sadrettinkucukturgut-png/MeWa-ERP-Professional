# ==========================================
# MeWa ERP Professional
# File : cari_model.py
# Version : 0.3
# ==========================================

import sqlite3


class CariModel:

    DB_PATH = "database/mewa.db"

    @classmethod
    def _ensure_contact_columns(cls):
        with sqlite3.connect(cls.DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(cariler)")
            existing = {str(row[1]).lower() for row in cursor.fetchall()}

            if "mobile" not in existing:
                cursor.execute("ALTER TABLE cariler ADD COLUMN mobile TEXT")
            if "whatsapp" not in existing:
                cursor.execute("ALTER TABLE cariler ADD COLUMN whatsapp TEXT")

            conn.commit()

    @classmethod
    def ekle(
        cls,
        cari_kodu,
        firma_unvani,
        yetkili,
        telefon,
        mobile,
        whatsapp,
        email,
        vergi_dairesi,
        vergi_no,
        ulke,
        sehir,
        ilce,
        adres
    ):

        cls._ensure_contact_columns()

        with sqlite3.connect(cls.DB_PATH) as conn:

            cursor = conn.cursor()

            cursor.execute("""

            INSERT INTO cariler(

                cari_kodu,
                firma_unvani,
                yetkili,
                telefon,
                mobile,
                whatsapp,
                email,
                vergi_dairesi,
                vergi_no,
                ulke,
                sehir,
                ilce,
                adres

            )

            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)

            """, (

                cari_kodu,
                firma_unvani,
                yetkili,
                telefon,
                mobile,
                whatsapp,
                email,
                vergi_dairesi,
                vergi_no,
                ulke,
                sehir,
                ilce,
                adres

            ))

            conn.commit()

    @classmethod
    def tum_cariler(cls):

        with sqlite3.connect(cls.DB_PATH) as conn:

            cursor = conn.cursor()

            cursor.execute("""

            SELECT

                cari_kodu,
                firma_unvani,
                yetkili,
                telefon,
                sehir

            FROM cariler

            ORDER BY firma_unvani

            """)

            return cursor.fetchall()

    @classmethod
    def getir(cls, cari_kodu):

        cls._ensure_contact_columns()

        with sqlite3.connect(cls.DB_PATH) as conn:

            cursor = conn.cursor()

            cursor.execute("""

            SELECT

                cari_kodu,
                firma_unvani,
                yetkili,
                telefon,
                COALESCE(mobile, ''),
                COALESCE(whatsapp, ''),
                email,
                vergi_dairesi,
                vergi_no,
                ulke,
                sehir,
                ilce,
                adres

            FROM cariler

            WHERE cari_kodu = ?

            """, (cari_kodu,))

            return cursor.fetchone()

    @classmethod
    def guncelle(
        cls,
        cari_kodu,
        firma_unvani,
        yetkili,
        telefon,
        mobile,
        whatsapp,
        email,
        vergi_dairesi,
        vergi_no,
        ulke,
        sehir,
        ilce,
        adres
    ):

        cls._ensure_contact_columns()

        with sqlite3.connect(cls.DB_PATH) as conn:

            cursor = conn.cursor()

            cursor.execute("""

            UPDATE cariler

            SET

                firma_unvani = ?,
                yetkili = ?,
                telefon = ?,
                mobile = ?,
                whatsapp = ?,
                email = ?,
                vergi_dairesi = ?,
                vergi_no = ?,
                ulke = ?,
                sehir = ?,
                ilce = ?,
                adres = ?

            WHERE cari_kodu = ?

            """, (

                firma_unvani,
                yetkili,
                telefon,
                mobile,
                whatsapp,
                email,
                vergi_dairesi,
                vergi_no,
                ulke,
                sehir,
                ilce,
                adres,
                cari_kodu

            ))

            conn.commit()

    @classmethod
    def sil(cls, cari_kodu):

        with sqlite3.connect(cls.DB_PATH) as conn:

            cursor = conn.cursor()

            cursor.execute("""

            DELETE FROM cariler

            WHERE cari_kodu = ?

            """, (cari_kodu,))

            conn.commit()

    @classmethod
    def tedarikci_lookup_kayitlari(cls):
        cls._ensure_contact_columns()
        with sqlite3.connect(cls.DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("PRAGMA table_info(cariler)")
            columns = {str(row[1]).lower() for row in cursor.fetchall()}

            def has_column(name):
                return name.lower() in columns

            select_parts = [
                "cari_kodu",
                "firma_unvani",
                "COALESCE(yetkili, '') AS yetkili",
                "COALESCE(telefon, '') AS telefon",
                "COALESCE(mobile, '') AS mobile",
                "COALESCE(whatsapp, '') AS whatsapp",
                "COALESCE(sehir, '') AS sehir",
                "COALESCE(ulke, '') AS ulke",
            ]

            if has_column("default_currency"):
                select_parts.append("COALESCE(default_currency, 'USD') AS default_currency")
            else:
                select_parts.append("'USD' AS default_currency")

            if has_column("payment_term"):
                select_parts.append("COALESCE(payment_term, '') AS payment_term")
            else:
                select_parts.append("'' AS payment_term")

            if has_column("vergi_no"):
                select_parts.append("COALESCE(vergi_no, '') AS vergi_no")
            else:
                select_parts.append("'' AS vergi_no")

            if has_column("cari_tipi"):
                select_parts.append("COALESCE(cari_tipi, '') AS cari_tipi")
            else:
                select_parts.append("'Tedarikçi' AS cari_tipi")

            query = f"SELECT {', '.join(select_parts)} FROM cariler"
            params = []
            if has_column("cari_tipi"):
                query += " WHERE LOWER(TRIM(COALESCE(cari_tipi, ''))) LIKE ?"
                params = ["%tedarik%"]
            query += " ORDER BY firma_unvani"

            cursor.execute(query, params)
            raw_rows = [dict(row) for row in cursor.fetchall()]

        try:
            from models.supplier_model import SupplierModel

            suppliers = SupplierModel.tum_tedarikciler()
        except Exception:
            suppliers = []

        by_code = {str(row.get("supplier_code") or "").strip().lower(): row for row in suppliers}
        by_name = {str(row.get("company_name") or "").strip().lower(): row for row in suppliers}

        normalized = []
        for row in raw_rows:
            cari_kodu = str(row.get("cari_kodu") or "").strip()
            firma_unvani = str(row.get("firma_unvani") or "").strip()
            if not cari_kodu and not firma_unvani:
                continue

            supplier = by_code.get(cari_kodu.lower()) or by_name.get(firma_unvani.lower())
            supplier_id = int(supplier.get("id") or 0) if supplier else 0

            normalized.append(
                {
                    "supplier_id": supplier_id,
                    "cari_kodu": cari_kodu,
                    "company_name": firma_unvani,
                    "firma_unvani": firma_unvani,
                    "contact_person": str(row.get("yetkili") or "").strip(),
                    "phone": str(row.get("telefon") or "").strip(),
                    "yetkili": str(row.get("yetkili") or "").strip(),
                    "telefon": str(row.get("telefon") or "").strip(),
                    "mobile": str(row.get("mobile") or "").strip(),
                    "whatsapp": str(row.get("whatsapp") or "").strip(),
                    "tax_number": str((row.get("vergi_no") or (supplier.get("tax_number") if supplier else "") or "")).strip(),
                    "vergi_no": str((row.get("vergi_no") or (supplier.get("tax_number") if supplier else "") or "")).strip(),
                    "city": str(row.get("sehir") or "").strip(),
                    "sehir": str(row.get("sehir") or "").strip(),
                    "country": str(row.get("ulke") or "").strip(),
                    "ulke": str(row.get("ulke") or "").strip(),
                    "cari_tipi": "Tedarikçi",
                    "default_currency": str((row.get("default_currency") or (supplier.get("default_currency") if supplier else "USD") or "USD")).strip() or "USD",
                    "payment_term": str((row.get("payment_term") or (supplier.get("payment_term") if supplier else "") or "")).strip(),
                }
            )

        return normalized

    @classmethod
    def lookup_kayitlari(cls):
        cls._ensure_contact_columns()
        with sqlite3.connect(cls.DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("PRAGMA table_info(cariler)")
            columns = {str(row[1]).lower() for row in cursor.fetchall()}

            def has_column(name):
                return name.lower() in columns

            select_parts = [
                "cari_kodu",
                "firma_unvani",
                "COALESCE(yetkili, '') AS yetkili",
                "COALESCE(telefon, '') AS telefon",
                "COALESCE(mobile, '') AS mobile",
                "COALESCE(whatsapp, '') AS whatsapp",
                "COALESCE(sehir, '') AS sehir",
                "COALESCE(ulke, '') AS ulke",
            ]

            if has_column("default_currency"):
                select_parts.append("COALESCE(default_currency, 'USD') AS default_currency")
            else:
                select_parts.append("'USD' AS default_currency")

            if has_column("payment_term"):
                select_parts.append("COALESCE(payment_term, '') AS payment_term")
            else:
                select_parts.append("'' AS payment_term")

            if has_column("vergi_no"):
                select_parts.append("COALESCE(vergi_no, '') AS vergi_no")
            else:
                select_parts.append("'' AS vergi_no")

            if has_column("cari_tipi"):
                select_parts.append("COALESCE(cari_tipi, '') AS cari_tipi")
            else:
                select_parts.append("'Cari' AS cari_tipi")

            query = f"SELECT {', '.join(select_parts)} FROM cariler ORDER BY firma_unvani"
            cursor.execute(query)
            raw_rows = [dict(row) for row in cursor.fetchall()]

        normalized = []
        for row in raw_rows:
            cari_kodu = str(row.get("cari_kodu") or "").strip()
            firma_unvani = str(row.get("firma_unvani") or "").strip()
            if not cari_kodu and not firma_unvani:
                continue

            normalized.append(
                {
                    "supplier_id": 0,
                    "cari_kodu": cari_kodu,
                    "company_name": firma_unvani,
                    "firma_unvani": firma_unvani,
                    "contact_person": str(row.get("yetkili") or "").strip(),
                    "phone": str(row.get("telefon") or "").strip(),
                    "yetkili": str(row.get("yetkili") or "").strip(),
                    "telefon": str(row.get("telefon") or "").strip(),
                    "mobile": str(row.get("mobile") or "").strip(),
                    "whatsapp": str(row.get("whatsapp") or "").strip(),
                    "tax_number": str(row.get("vergi_no") or "").strip(),
                    "vergi_no": str(row.get("vergi_no") or "").strip(),
                    "city": str(row.get("sehir") or "").strip(),
                    "sehir": str(row.get("sehir") or "").strip(),
                    "country": str(row.get("ulke") or "").strip(),
                    "ulke": str(row.get("ulke") or "").strip(),
                    "cari_tipi": str(row.get("cari_tipi") or "Cari").strip() or "Cari",
                    "default_currency": str(row.get("default_currency") or "USD").strip() or "USD",
                    "payment_term": str(row.get("payment_term") or "").strip(),
                }
            )

        return normalized

    @classmethod
    def telefon_bilgisi(cls, cari_kodu):
        cls._ensure_contact_columns()
        with sqlite3.connect(cls.DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT
                    COALESCE(whatsapp, ''),
                    COALESCE(mobile, ''),
                    COALESCE(telefon, '')
                FROM cariler
                WHERE cari_kodu = ?
                """,
                (cari_kodu,),
            )
            row = cursor.fetchone()
            if row is None:
                return ""
            whatsapp = str(row[0] or "").strip()
            mobile = str(row[1] or "").strip()
            phone = str(row[2] or "").strip()
            return whatsapp or mobile or phone