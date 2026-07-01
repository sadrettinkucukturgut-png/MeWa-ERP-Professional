from __future__ import annotations

import re
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any


class CompanyProfileModel:
    db_path = str(Path(__file__).resolve().parent.parent / "database" / "mewa.db")
    table_name = "company_profile"

    PROFILE_FIELDS = [
        "company_name",
        "company_short_name",
        "tax_office",
        "tax_number",
        "mersis_number",
        "trade_registry_number",
        "phone",
        "mobile",
        "whatsapp",
        "email",
        "website",
        "address",
        "factory_address",
        "city",
        "postal_code",
        "country",
        "bank_name",
        "iban",
        "swift",
        "currency",
        "logo_path",
        "stamp_path",
        "signature_path",
    ]

    DEFAULT_RECORD: dict[str, str] = {
        "company_name": "MeWa Automotive Ltd. Şti.",
        "company_short_name": "",
        "tax_office": "",
        "tax_number": "",
        "mersis_number": "",
        "trade_registry_number": "",
        "phone": "",
        "mobile": "",
        "whatsapp": "",
        "email": "",
        "website": "",
        "address": "",
        "factory_address": "",
        "city": "Konya",
        "postal_code": "",
        "country": "Turkey",
        "bank_name": "",
        "iban": "",
        "swift": "",
        "currency": "USD",
        "logo_path": "",
        "stamp_path": "",
        "signature_path": "",
    }

    _asset_name_by_type = {
        "logo": "company_logo",
        "stamp": "company_stamp",
        "signature": "company_signature",
    }

    @classmethod
    def _connect(cls) -> sqlite3.Connection:
        return sqlite3.connect(cls.db_path)

    @staticmethod
    def _now() -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    @classmethod
    def ensure_schema(cls) -> None:
        with cls._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS company_profile(
                    id INTEGER PRIMARY KEY,
                    company_name TEXT,
                    company_short_name TEXT,
                    tax_office TEXT,
                    tax_number TEXT,
                    mersis_number TEXT,
                    trade_registry_number TEXT,
                    phone TEXT,
                    mobile TEXT,
                    whatsapp TEXT,
                    email TEXT,
                    website TEXT,
                    address TEXT,
                    factory_address TEXT,
                    city TEXT,
                    postal_code TEXT,
                    country TEXT,
                    bank_name TEXT,
                    iban TEXT,
                    swift TEXT,
                    currency TEXT,
                    logo_path TEXT,
                    stamp_path TEXT,
                    signature_path TEXT,
                    created_at TEXT,
                    updated_at TEXT
                )
                """
            )

            cursor.execute("PRAGMA table_info(company_profile)")
            existing_columns = {str(row[1]).strip().lower() for row in cursor.fetchall()}
            expected_text_columns = set(cls.PROFILE_FIELDS + ["created_at", "updated_at"])
            for column in expected_text_columns:
                if column not in existing_columns:
                    cursor.execute(f"ALTER TABLE company_profile ADD COLUMN {column} TEXT")

            cls._ensure_single_record(cursor)
            conn.commit()

    @classmethod
    def _ensure_single_record(cls, cursor: sqlite3.Cursor) -> int:
        cursor.execute("SELECT id FROM company_profile ORDER BY id")
        ids = [int(row[0]) for row in cursor.fetchall()]

        if not ids:
            now = cls._now()
            columns = ["id", *cls.PROFILE_FIELDS, "created_at", "updated_at"]
            values = [1, *[cls.DEFAULT_RECORD.get(field, "") for field in cls.PROFILE_FIELDS], now, now]
            placeholders = ", ".join(["?" for _ in columns])
            cursor.execute(
                f"INSERT INTO company_profile({', '.join(columns)}) VALUES({placeholders})",
                values,
            )
            return 1

        keep_id = ids[0]
        if len(ids) > 1:
            placeholders = ", ".join(["?" for _ in ids[1:]])
            cursor.execute(f"DELETE FROM company_profile WHERE id IN ({placeholders})", ids[1:])
        return keep_id

    @classmethod
    def get_profile(cls) -> dict[str, Any]:
        cls.ensure_schema()
        with cls._connect() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            keep_id = cls._ensure_single_record(cursor)
            cursor.execute("SELECT * FROM company_profile WHERE id = ? LIMIT 1", (keep_id,))
            row = cursor.fetchone()
            conn.commit()
            if row is None:
                return {"id": keep_id, **cls.DEFAULT_RECORD}

            data = dict(row)
            for field in cls.PROFILE_FIELDS:
                data[field] = str(data.get(field) or "")
            data.setdefault("id", keep_id)
            data.setdefault("created_at", "")
            data.setdefault("updated_at", "")
            return data

    @classmethod
    def update_profile(cls, values: dict[str, Any]) -> dict[str, Any]:
        cls.ensure_schema()
        payload: dict[str, str] = {}
        for field in cls.PROFILE_FIELDS:
            if field in values:
                payload[field] = str(values.get(field) or "").strip()

        company_name = payload.get("company_name", "") or str(values.get("company_name") or "").strip()
        if not company_name:
            raise ValueError("Company Name is mandatory.")

        with cls._connect() as conn:
            cursor = conn.cursor()
            keep_id = cls._ensure_single_record(cursor)
            if payload:
                assignments = ", ".join([f"{key} = ?" for key in payload.keys()])
                params = [*payload.values(), cls._now(), keep_id]
                cursor.execute(
                    f"UPDATE company_profile SET {assignments}, updated_at = ? WHERE id = ?",
                    params,
                )
            conn.commit()

        return cls.get_profile()

    @classmethod
    def restore_defaults(cls) -> dict[str, Any]:
        cls.ensure_schema()
        with cls._connect() as conn:
            cursor = conn.cursor()
            keep_id = cls._ensure_single_record(cursor)
            assignments = ", ".join([f"{field} = ?" for field in cls.PROFILE_FIELDS])
            values = [cls.DEFAULT_RECORD.get(field, "") for field in cls.PROFILE_FIELDS]
            cursor.execute(
                f"UPDATE company_profile SET {assignments}, updated_at = ? WHERE id = ?",
                [*values, cls._now(), keep_id],
            )
            conn.commit()
        return cls.get_profile()

    @classmethod
    def format_phone(cls, value: str) -> str:
        text = str(value or "").strip()
        if not text:
            return ""
        keep_plus = text.startswith("+")
        digits = "".join(ch for ch in text if ch.isdigit())
        if keep_plus and digits:
            return f"+{digits}"
        return digits

    @classmethod
    def format_iban(cls, value: str) -> str:
        compact = re.sub(r"\s+", "", str(value or "")).upper()
        if not compact:
            return ""
        return " ".join(compact[i : i + 4] for i in range(0, len(compact), 4))

    @staticmethod
    def is_valid_email(value: str) -> bool:
        text = str(value or "").strip()
        if not text:
            return True
        return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", text))

    @staticmethod
    def is_valid_website(value: str) -> bool:
        text = str(value or "").strip()
        if not text:
            return True
        return bool(re.match(r"^(https?://)?[A-Za-z0-9.-]+\.[A-Za-z]{2,}(/.*)?$", text))

    @classmethod
    def to_relative_path(cls, path: str) -> str:
        if not path:
            return ""
        try:
            project_root = Path(__file__).resolve().parent.parent
            candidate = Path(path)
            if candidate.is_absolute():
                rel = candidate.relative_to(project_root)
                return str(rel).replace("\\", "/")
        except Exception:
            pass
        return str(path).replace("\\", "/")

    @classmethod
    def resolve_path(cls, stored_path: str) -> Path:
        text = str(stored_path or "").strip()
        if not text:
            return Path("")
        candidate = Path(text)
        if candidate.is_absolute():
            return candidate
        return Path(__file__).resolve().parent.parent / candidate

    @classmethod
    def copy_branding_asset(cls, source_path: str, asset_type: str) -> str:
        source = Path(source_path)
        if not source.exists() or not source.is_file():
            raise ValueError("Selected file does not exist.")

        key = cls._asset_name_by_type.get(str(asset_type or "").strip().lower())
        if not key:
            raise ValueError("Unsupported branding asset type.")

        branding_dir = Path(__file__).resolve().parent.parent / "assets" / "branding"
        branding_dir.mkdir(parents=True, exist_ok=True)

        ext = source.suffix.lower() if source.suffix else ".png"
        target = branding_dir / f"{key}{ext}"
        shutil.copy2(source, target)
        return cls.to_relative_path(str(target))

    @classmethod
    def get_document_profile(cls) -> dict[str, str]:
        profile = cls.get_profile()
        head_address_parts = [
            str(profile.get("address") or "").strip(),
            str(profile.get("city") or "").strip(),
            str(profile.get("postal_code") or "").strip(),
            str(profile.get("country") or "").strip(),
        ]
        company_address = ", ".join([part for part in head_address_parts if part])

        phone = str(profile.get("phone") or "").strip()
        whatsapp = str(profile.get("whatsapp") or "").strip()
        mobile = str(profile.get("mobile") or "").strip()
        if not phone:
            phone = mobile or whatsapp

        bank_name = str(profile.get("bank_name") or "").strip()
        iban = str(profile.get("iban") or "").strip()
        swift = str(profile.get("swift") or "").strip()

        bank_parts = []
        if bank_name:
            bank_parts.append(f"Bank: {bank_name}")
        if iban:
            bank_parts.append(f"IBAN: {iban}")
        if swift:
            bank_parts.append(f"SWIFT: {swift}")

        return {
            "company_name": str(profile.get("company_name") or cls.DEFAULT_RECORD["company_name"]),
            "company_short_name": str(profile.get("company_short_name") or "").strip(),
            "company_address": company_address,
            "factory_address": str(profile.get("factory_address") or "").strip(),
            "city": str(profile.get("city") or "").strip(),
            "postal_code": str(profile.get("postal_code") or "").strip(),
            "country": str(profile.get("country") or "").strip(),
            "phone": phone,
            "mobile": mobile,
            "whatsapp": whatsapp,
            "email": str(profile.get("email") or "").strip(),
            "website": str(profile.get("website") or "").strip(),
            "tax_office": str(profile.get("tax_office") or "").strip(),
            "tax_number": str(profile.get("tax_number") or "").strip(),
            "currency": str(profile.get("currency") or cls.DEFAULT_RECORD["currency"]),
            "bank_name": bank_name,
            "iban": iban,
            "swift": swift,
            "bank_information": " | ".join(bank_parts),
            "logo_path": str(profile.get("logo_path") or "").strip(),
            "stamp_path": str(profile.get("stamp_path") or "").strip(),
            "signature_path": str(profile.get("signature_path") or "").strip(),
        }
