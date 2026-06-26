# ==========================================
# MeWa ERP Professional
# File : cari_model.py
# Version : 0.3
# ==========================================

import sqlite3


class CariModel:

    DB_PATH = "database/mewa.db"

    @classmethod
    def ekle(
        cls,
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
    ):

        with sqlite3.connect(cls.DB_PATH) as conn:

            cursor = conn.cursor()

            cursor.execute("""

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

            )

            VALUES(?,?,?,?,?,?,?,?,?,?,?)

            """, (

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

        with sqlite3.connect(cls.DB_PATH) as conn:

            cursor = conn.cursor()

            cursor.execute("""

            SELECT

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
        email,
        vergi_dairesi,
        vergi_no,
        ulke,
        sehir,
        ilce,
        adres
    ):

        with sqlite3.connect(cls.DB_PATH) as conn:

            cursor = conn.cursor()

            cursor.execute("""

            UPDATE cariler

            SET

                firma_unvani = ?,
                yetkili = ?,
                telefon = ?,
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