from __future__ import annotations

import sqlite3
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.crud_base import BaseCrud


class BaseDocumentModel(BaseCrud, ABC):
    """Common model contract for commercial documents."""

    @staticmethod
    def now() -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def rows_to_dicts(cursor, rows) -> List[Dict[str, Any]]:
        columns = [column[0] for column in cursor.description] if cursor.description else []
        return [dict(zip(columns, row)) for row in rows]

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

        company = str(firma_unvani or "").strip()
        code = str(cari_kodu or "").strip()
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

    @abstractmethod
    def list_invoices(self, keyword: str = "") -> List[Dict[str, Any]]:  # pragma: no cover - interface
        raise NotImplementedError

    @abstractmethod
    def invoice_detail(self, invoice_number: str) -> Optional[Dict[str, Any]]:  # pragma: no cover - interface
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def invoice_number_generate(cls) -> str:  # pragma: no cover - interface
        raise NotImplementedError
