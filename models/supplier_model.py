from pathlib import Path
from typing import Any, Dict, List, Optional

from core.crud_base import BaseCrud


class SupplierModel(BaseCrud):
    db_path = str(Path(__file__).resolve().parent.parent / "database" / "mewa.db")
    table_name = "suppliers"
    id_field = "id"

    @classmethod
    def ekle(
        cls,
        supplier_code: str,
        company_name: str,
        contact_person: str,
        phone: str = "",
        whatsapp: str = "",
        email: str = "",
        website: str = "",
        tax_office: str = "",
        tax_number: str = "",
        country: str = "",
        city: str = "",
        district: str = "",
        address: str = "",
        default_currency: str = "USD",
        payment_term: str = "",
        bank_name: str = "",
        iban: str = "",
        swift_code: str = "",
        notes: str = "",
    ) -> int:
        return cls().insert(
            {
                "supplier_code": supplier_code,
                "company_name": company_name,
                "contact_person": contact_person,
                "phone": phone,
                "whatsapp": whatsapp,
                "email": email,
                "website": website,
                "tax_office": tax_office,
                "tax_number": tax_number,
                "country": country,
                "city": city,
                "district": district,
                "address": address,
                "default_currency": default_currency or "USD",
                "payment_term": payment_term,
                "bank_name": bank_name,
                "iban": iban,
                "swift_code": swift_code,
                "notes": notes,
            }
        )

    @classmethod
    def getir(cls, supplier_code: str) -> Optional[Dict[str, Any]]:
        with cls()._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"SELECT * FROM {cls.table_name} WHERE supplier_code = ?",
                (supplier_code,),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            columns = [column[1] for column in cursor.description] if cursor.description else []
            return dict(zip(columns, row))

    @classmethod
    def guncelle(
        cls,
        existing_supplier_code: str,
        supplier_code: str,
        company_name: str,
        contact_person: str,
        phone: str = "",
        whatsapp: str = "",
        email: str = "",
        website: str = "",
        tax_office: str = "",
        tax_number: str = "",
        country: str = "",
        city: str = "",
        district: str = "",
        address: str = "",
        default_currency: str = "USD",
        payment_term: str = "",
        bank_name: str = "",
        iban: str = "",
        swift_code: str = "",
        notes: str = "",
    ) -> None:
        record = cls.getir(existing_supplier_code)
        if record is None:
            raise ValueError("Tedarikçi bulunamadı")

        cls().update(
            int(record["id"]),
            {
                "supplier_code": supplier_code or existing_supplier_code,
                "company_name": company_name,
                "contact_person": contact_person,
                "phone": phone,
                "whatsapp": whatsapp,
                "email": email,
                "website": website,
                "tax_office": tax_office,
                "tax_number": tax_number,
                "country": country,
                "city": city,
                "district": district,
                "address": address,
                "default_currency": default_currency or "USD",
                "payment_term": payment_term,
                "bank_name": bank_name,
                "iban": iban,
                "swift_code": swift_code,
                "notes": notes,
            },
        )

    @classmethod
    def sil(cls, supplier_code: str) -> None:
        record = cls.getir(supplier_code)
        if record is None:
            return
        cls().delete(int(record["id"]))

    @classmethod
    def tum_tedarikciler(cls) -> List[Dict[str, Any]]:
        return cls().load_all(order_by="company_name")

    @classmethod
    def ara(cls, keyword: str = "") -> List[Dict[str, Any]]:
        if not keyword or not keyword.strip():
            return cls().load_all(order_by="company_name")

        keyword_value = f"%{keyword.strip()}%"
        with cls()._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"""
                SELECT * FROM {cls.table_name}
                WHERE LOWER(supplier_code) LIKE ?
                   OR LOWER(company_name) LIKE ?
                   OR LOWER(contact_person) LIKE ?
                   OR LOWER(phone) LIKE ?
                   OR LOWER(whatsapp) LIKE ?
                   OR LOWER(email) LIKE ?
                   OR LOWER(city) LIKE ?
                   OR LOWER(country) LIKE ?
                ORDER BY company_name
                """,
                [keyword_value.lower() for _ in range(8)],
            )
            columns = [column[1] for column in cursor.description] if cursor.description else []
            rows = cursor.fetchall()
            return [dict(zip(columns, row)) for row in rows]

    @classmethod
    def supplier_code_exists(cls, supplier_code: str, exclude_code: Optional[str] = None) -> bool:
        if not supplier_code:
            return False
        with cls()._connect() as conn:
            cursor = conn.cursor()
            if exclude_code:
                cursor.execute(
                    f"SELECT 1 FROM {cls.table_name} WHERE supplier_code = ? AND supplier_code != ?",
                    (supplier_code, exclude_code),
                )
            else:
                cursor.execute(f"SELECT 1 FROM {cls.table_name} WHERE supplier_code = ?", (supplier_code,))
            return cursor.fetchone() is not None
