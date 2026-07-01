from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from services.accounting_posting_service import AccountingPostingService


class FinanceModel:
    DB_PATH = str(Path(__file__).resolve().parent.parent / "database" / "mewa.db")
    _column_cache: dict[str, set[str]] = {}
    _listeners: list[Callable[[str], None]] = []

    @classmethod
    def _connect(cls):
        conn = sqlite3.connect(cls.DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    @staticmethod
    def _now_date() -> str:
        return datetime.now().strftime("%Y-%m-%d")

    @staticmethod
    def _rows_to_dicts(rows) -> list[dict[str, Any]]:
        return [dict(row) for row in rows]

    @classmethod
    def register_listener(cls, callback: Callable[[str], None]) -> None:
        if callback not in cls._listeners:
            cls._listeners.append(callback)

    @classmethod
    def unregister_listener(cls, callback: Callable[[str], None]) -> None:
        cls._listeners = [fn for fn in cls._listeners if fn is not callback]

    @classmethod
    def _notify(cls, event: str) -> None:
        for callback in list(cls._listeners):
            try:
                callback(event)
            except Exception:
                continue

    @classmethod
    def notify_change(cls, event: str) -> None:
        cls._notify(event)

    @staticmethod
    def _begin_transaction(conn) -> None:
        conn.execute("BEGIN TRANSACTION")

    @classmethod
    def _table_columns(cls, *, conn, table_name: str) -> set[str]:
        key = str(table_name or "").strip().lower()
        cached = cls._column_cache.get(key)
        if cached is not None:
            return cached

        cur = conn.cursor()
        cur.execute(f"PRAGMA table_info({key})")
        cols = {str(row[1]).strip().lower() for row in cur.fetchall()}
        cls._column_cache[key] = cols
        return cols

    @classmethod
    def _has_column(cls, *, conn, table_name: str, column_name: str) -> bool:
        return str(column_name or "").strip().lower() in cls._table_columns(conn=conn, table_name=table_name)

    @classmethod
    def next_cash_code(cls) -> str:
        with cls._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT COALESCE(cash_code, '')
                FROM cash_accounts
                WHERE cash_code LIKE 'KASA-%'
                ORDER BY cash_code DESC
                LIMIT 1
                """
            )
            row = cur.fetchone()
        if row is None:
            return "KASA-0001"
        txt = str(row[0] or "")
        try:
            seq = int(txt.split("-")[-1]) + 1
        except Exception:
            seq = 1
        return f"KASA-{seq:04d}"

    @classmethod
    def next_bank_code(cls) -> str:
        with cls._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT COALESCE(bank_code, '')
                FROM bank_accounts
                WHERE bank_code LIKE 'BNK-%'
                ORDER BY bank_code DESC
                LIMIT 1
                """
            )
            row = cur.fetchone()
        if row is None:
            return "BNK-0001"
        txt = str(row[0] or "")
        try:
            seq = int(txt.split("-")[-1]) + 1
        except Exception:
            seq = 1
        return f"BNK-{seq:04d}"

    @classmethod
    def customer_account_currency(cls, customer_id: int, *, conn=None) -> str:
        if int(customer_id or 0) <= 0:
            return "USD"

        owns_conn = conn is None
        db = conn or cls._connect()
        try:
            cur = db.cursor()
            if cls._has_column(conn=db, table_name="cariler", column_name="default_currency"):
                cur.execute("SELECT COALESCE(default_currency, 'USD') FROM cariler WHERE id = ?", (int(customer_id),))
                row = cur.fetchone()
                return str((row[0] if row else "USD") or "USD").strip().upper() or "USD"
            return "USD"
        finally:
            if owns_conn:
                db.close()

    @classmethod
    def supplier_account_currency(cls, supplier_id: int, *, conn=None) -> str:
        if int(supplier_id or 0) <= 0:
            return "USD"

        owns_conn = conn is None
        db = conn or cls._connect()
        try:
            cur = db.cursor()
            if cls._has_column(conn=db, table_name="suppliers", column_name="default_currency"):
                cur.execute("SELECT COALESCE(default_currency, 'USD') FROM suppliers WHERE id = ?", (int(supplier_id),))
                row = cur.fetchone()
                return str((row[0] if row else "USD") or "USD").strip().upper() or "USD"
            return "USD"
        finally:
            if owns_conn:
                db.close()

    @classmethod
    def customer_balance(cls, customer_id: int) -> float:
        if int(customer_id or 0) <= 0:
            return 0.0
        with cls._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT COALESCE(SUM(COALESCE(amount, 0)), 0)
                FROM customer_account_movements
                WHERE customer_id = ?
                  AND LOWER(COALESCE(status, '')) != 'cancelled'
                """,
                (int(customer_id),),
            )
            row = cur.fetchone()
            return float((row[0] if row else 0) or 0)

    @classmethod
    def customer_summary(cls, customer_id: int) -> dict[str, Any]:
        if int(customer_id or 0) <= 0:
            return {"customer_id": 0, "code": "", "name": "", "currency": "USD", "balance": 0.0}

        with cls._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT id, COALESCE(cari_kodu, '') AS code, COALESCE(firma_unvani, '') AS name
                FROM cariler
                WHERE id = ?
                """,
                (int(customer_id),),
            )
            row = cur.fetchone()
            if row is None:
                return {"customer_id": 0, "code": "", "name": "", "currency": "USD", "balance": 0.0}
            return {
                "customer_id": int(row["id"] or 0),
                "code": str(row["code"] or ""),
                "name": str(row["name"] or ""),
                "currency": cls.customer_account_currency(int(row["id"] or 0), conn=conn),
                "balance": cls.customer_balance(int(row["id"] or 0)),
            }

    @classmethod
    def _convert_amount_for_account(
        cls,
        *,
        amount: float,
        voucher_currency: str,
        account_currency: str,
        exchange_rate: float | None,
    ) -> tuple[float, float]:
        voucher_curr = str(voucher_currency or "USD").strip().upper() or "USD"
        account_curr = str(account_currency or "USD").strip().upper() or "USD"

        if voucher_curr == account_curr:
            return float(amount), 1.0

        rate = float(exchange_rate or 0)
        if rate <= 0:
            raise ValueError(f"EXCHANGE_RATE_REQUIRED|{account_curr}|{voucher_curr}")

        return float(amount) * rate, rate

    @classmethod
    def _next_no(cls, table: str, field: str, prefix: str) -> str:
        day = datetime.now().strftime("%Y%m%d")
        base = f"{prefix}-{day}-"
        with cls._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                f"SELECT {field} FROM {table} WHERE {field} LIKE ? ORDER BY {field} DESC LIMIT 1",
                (f"{base}%",),
            )
            row = cur.fetchone()
        if row is None:
            return f"{base}0001"
        txt = str(row[0] or "")
        try:
            seq = int(txt.split("-")[-1]) + 1
        except Exception:
            seq = 1
        return f"{base}{seq:04d}"

    @classmethod
    def list_cash_accounts(cls, keyword: str = "") -> list[dict[str, Any]]:
        params: list[Any] = []
        where = ""
        if keyword.strip():
            token = f"%{keyword.strip().lower()}%"
            where = "WHERE LOWER(cash_code) LIKE ? OR LOWER(cash_name) LIKE ? OR LOWER(currency) LIKE ?"
            params = [token, token, token]

        with cls._connect() as conn:
            cur = conn.cursor()
            created_expr = "COALESCE(created_at, '')" if cls._has_column(conn=conn, table_name="cash_accounts", column_name="created_at") else "''"
            cur.execute(
                f"""
                SELECT id, cash_code, cash_name, currency,
                       COALESCE(opening_balance, 0) AS opening_balance,
                       COALESCE(current_balance, 0) AS current_balance,
                       COALESCE(opening_date, '') AS opening_date,
                       COALESCE(notes, '') AS notes,
                       {created_expr} AS created_at
                FROM cash_accounts
                {where}
                ORDER BY cash_name
                """,
                params,
            )
            return cls._rows_to_dicts(cur.fetchall())

    @classmethod
    def save_cash_account(cls, *, cash_id: int | None, cash_code: str, cash_name: str, currency: str, opening_balance: float, opening_date: str, notes: str) -> int:
        code = str(cash_code or "").strip()
        name = str(cash_name or "").strip()
        if not code or not name:
            raise ValueError("Cash code and name are required")

        with cls._connect() as conn:
            cur = conn.cursor()
            cls._begin_transaction(conn)
            if cash_id:
                cur.execute(
                    """
                    UPDATE cash_accounts
                    SET cash_code = ?, cash_name = ?, currency = ?, opening_balance = ?, opening_date = ?, notes = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (code, name, currency, float(opening_balance or 0), opening_date, notes, int(cash_id)),
                )
                conn.commit()
                cls._notify("cash-account")
                return int(cash_id)

            cur.execute(
                """
                INSERT INTO cash_accounts(cash_code, cash_name, currency, opening_balance, current_balance, opening_date, notes)
                VALUES(?,?,?,?,?,?,?)
                """,
                (code, name, currency, float(opening_balance or 0), float(opening_balance or 0), opening_date, notes),
            )
            conn.commit()
            cls._notify("cash-account")
            return int(cur.lastrowid)

    @classmethod
    def delete_cash_account(cls, cash_id: int) -> None:
        with cls._connect() as conn:
            cur = conn.cursor()
            cls._begin_transaction(conn)
            cur.execute("DELETE FROM cash_accounts WHERE id = ?", (int(cash_id),))
            conn.commit()
        cls._notify("cash-account")

    @classmethod
    def list_bank_accounts(cls, keyword: str = "") -> list[dict[str, Any]]:
        params: list[Any] = []
        where = ""
        if keyword.strip():
            token = f"%{keyword.strip().lower()}%"
            where = """
            WHERE LOWER(bank_code) LIKE ? OR LOWER(bank_name) LIKE ? OR LOWER(COALESCE(branch_name, '')) LIKE ?
               OR LOWER(COALESCE(iban, '')) LIKE ? OR LOWER(COALESCE(swift_code, '')) LIKE ?
            """
            params = [token, token, token, token, token]

        with cls._connect() as conn:
            cur = conn.cursor()
            created_expr = "COALESCE(created_at, '')" if cls._has_column(conn=conn, table_name="bank_accounts", column_name="created_at") else "''"
            cur.execute(
                f"""
                SELECT id, bank_code, bank_name, COALESCE(branch_name, '') AS branch_name,
                       COALESCE(iban, '') AS iban, COALESCE(swift_code, '') AS swift_code,
                       COALESCE(account_number, '') AS account_number,
                       currency,
                       COALESCE(opening_balance, 0) AS opening_balance,
                       COALESCE(current_balance, 0) AS current_balance,
                       COALESCE(opening_date, '') AS opening_date,
                       COALESCE(notes, '') AS notes,
                       {created_expr} AS created_at
                FROM bank_accounts
                {where}
                ORDER BY bank_name
                """,
                params,
            )
            return cls._rows_to_dicts(cur.fetchall())

    @classmethod
    def ensure_default_bank_accounts(cls) -> None:
        defaults = [
            ("BNK-TRY", "Main Bank TRY", "TRY"),
            ("BNK-USD", "Main Bank USD", "USD"),
            ("BNK-EUR", "Main Bank EUR", "EUR"),
        ]
        with cls._connect() as conn:
            cur = conn.cursor()
            for code, name, curr in defaults:
                cur.execute("SELECT id FROM bank_accounts WHERE bank_code = ? LIMIT 1", (code,))
                if cur.fetchone() is not None:
                    continue
                cur.execute(
                    """
                    INSERT INTO bank_accounts(
                        bank_code, bank_name, branch_name, iban, swift_code, account_number,
                        currency, opening_balance, current_balance, opening_date, notes
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        code,
                        name,
                        "",
                        "",
                        "",
                        "",
                        curr,
                        0.0,
                        0.0,
                        cls._now_date(),
                        "Auto-created default bank account",
                    ),
                )
            conn.commit()

    @classmethod
    def save_bank_account(
        cls,
        *,
        bank_id: int | None,
        bank_code: str,
        bank_name: str,
        branch_name: str,
        iban: str,
        swift_code: str,
        account_number: str,
        currency: str,
        opening_balance: float,
        opening_date: str,
        notes: str,
    ) -> int:
        code = str(bank_code or "").strip()
        name = str(bank_name or "").strip()
        if not code or not name:
            raise ValueError("Bank code and name are required")

        with cls._connect() as conn:
            cur = conn.cursor()
            cls._begin_transaction(conn)
            if bank_id:
                cur.execute(
                    """
                    UPDATE bank_accounts
                    SET bank_code=?, bank_name=?, branch_name=?, iban=?, swift_code=?, account_number=?,
                        currency=?, opening_balance=?, opening_date=?, notes=?, updated_at=CURRENT_TIMESTAMP
                    WHERE id=?
                    """,
                    (
                        code,
                        name,
                        branch_name,
                        iban,
                        swift_code,
                        account_number,
                        currency,
                        float(opening_balance or 0),
                        opening_date,
                        notes,
                        int(bank_id),
                    ),
                )
                conn.commit()
                cls._notify("bank-account")
                return int(bank_id)

            cur.execute(
                """
                INSERT INTO bank_accounts(
                    bank_code, bank_name, branch_name, iban, swift_code, account_number,
                    currency, opening_balance, current_balance, opening_date, notes
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    code,
                    name,
                    branch_name,
                    iban,
                    swift_code,
                    account_number,
                    currency,
                    float(opening_balance or 0),
                    float(opening_balance or 0),
                    opening_date,
                    notes,
                ),
            )
            conn.commit()
            cls._notify("bank-account")
            return int(cur.lastrowid)

    @classmethod
    def delete_bank_account(cls, bank_id: int) -> None:
        with cls._connect() as conn:
            cur = conn.cursor()
            cls._begin_transaction(conn)
            cur.execute("DELETE FROM bank_accounts WHERE id = ?", (int(bank_id),))
            conn.commit()
        cls._notify("bank-account")

    @classmethod
    def cash_account_has_transactions(cls, cash_id: int) -> bool:
        cid = int(cash_id or 0)
        if cid <= 0:
            return False
        with cls._connect() as conn:
            cur = conn.cursor()
            cls._begin_transaction(conn)
            checks = [
                ("SELECT 1 FROM cash_transactions WHERE cash_account_id = ? LIMIT 1", (cid,)),
                ("SELECT 1 FROM customer_collections WHERE cash_account_id = ? LIMIT 1", (cid,)),
                ("SELECT 1 FROM supplier_payments WHERE cash_account_id = ? LIMIT 1", (cid,)),
                ("SELECT 1 FROM finance_transactions WHERE cash_account_id = ? LIMIT 1", (cid,)),
            ]
            for query, params in checks:
                cur.execute(query, params)
                if cur.fetchone() is not None:
                    return True
        return False

    @classmethod
    def bank_account_has_transactions(cls, bank_id: int) -> bool:
        bid = int(bank_id or 0)
        if bid <= 0:
            return False
        with cls._connect() as conn:
            cur = conn.cursor()
            cls._begin_transaction(conn)
            checks = [
                ("SELECT 1 FROM bank_transactions WHERE bank_account_id = ? LIMIT 1", (bid,)),
                ("SELECT 1 FROM customer_collections WHERE bank_account_id = ? LIMIT 1", (bid,)),
                ("SELECT 1 FROM supplier_payments WHERE bank_account_id = ? LIMIT 1", (bid,)),
                ("SELECT 1 FROM finance_transactions WHERE bank_account_id = ? LIMIT 1", (bid,)),
            ]
            for query, params in checks:
                cur.execute(query, params)
                if cur.fetchone() is not None:
                    return True
        return False

    @classmethod
    def post_cash_movement(
        cls,
        *,
        movement_type: str,
        transaction_date: str,
        amount: float,
        currency: str,
        source_cash_account_id: int | None,
        target_cash_account_id: int | None,
        target_bank_account_id: int | None,
        reference_no: str,
        description: str,
    ) -> None:
        mtype = str(movement_type or "").strip().upper()
        if mtype not in {"CASH_IN", "CASH_OUT", "TRANSFER"}:
            raise ValueError("Unsupported cash movement type")
        if float(amount or 0) <= 0:
            raise ValueError("Amount must be greater than 0")

        with cls._connect() as conn:
            cur = conn.cursor()
            cls._begin_transaction(conn)

            if mtype == "CASH_IN":
                if not source_cash_account_id:
                    raise ValueError("Cash account is required for Cash In")
                cur.execute(
                    "UPDATE cash_accounts SET current_balance = COALESCE(current_balance, 0) + ? WHERE id = ?",
                    (float(amount), int(source_cash_account_id)),
                )
                cls._post_finance_transaction(
                    conn=conn,
                    transaction_date=transaction_date,
                    transaction_type="CASH_IN",
                    account_type="CASH",
                    cash_account_id=int(source_cash_account_id),
                    bank_account_id=None,
                    customer_id=None,
                    supplier_id=None,
                    currency=currency,
                    debit=float(amount),
                    credit=0.0,
                    reference_no=reference_no,
                    document_no="",
                    description=description or "Cash In",
                )

            elif mtype == "CASH_OUT":
                if not source_cash_account_id:
                    raise ValueError("Cash account is required for Cash Out")
                cur.execute(
                    "UPDATE cash_accounts SET current_balance = COALESCE(current_balance, 0) - ? WHERE id = ?",
                    (float(amount), int(source_cash_account_id)),
                )
                cls._post_finance_transaction(
                    conn=conn,
                    transaction_date=transaction_date,
                    transaction_type="CASH_OUT",
                    account_type="CASH",
                    cash_account_id=int(source_cash_account_id),
                    bank_account_id=None,
                    customer_id=None,
                    supplier_id=None,
                    currency=currency,
                    debit=0.0,
                    credit=float(amount),
                    reference_no=reference_no,
                    document_no="",
                    description=description or "Cash Out",
                )

            else:
                if not source_cash_account_id:
                    raise ValueError("Source cash account is required for Transfer")
                if not target_cash_account_id and not target_bank_account_id:
                    raise ValueError("Target cash or bank account is required for Transfer")

                cur.execute(
                    "UPDATE cash_accounts SET current_balance = COALESCE(current_balance, 0) - ? WHERE id = ?",
                    (float(amount), int(source_cash_account_id)),
                )

                if target_cash_account_id:
                    cur.execute(
                        "UPDATE cash_accounts SET current_balance = COALESCE(current_balance, 0) + ? WHERE id = ?",
                        (float(amount), int(target_cash_account_id)),
                    )
                    cls._post_finance_transaction(
                        conn=conn,
                        transaction_date=transaction_date,
                        transaction_type="TRANSFER_IN",
                        account_type="CASH",
                        cash_account_id=int(target_cash_account_id),
                        bank_account_id=None,
                        customer_id=None,
                        supplier_id=None,
                        currency=currency,
                        debit=float(amount),
                        credit=0.0,
                        reference_no=reference_no,
                        document_no="",
                        description=description or "Transfer In",
                    )

                if target_bank_account_id:
                    cur.execute(
                        "UPDATE bank_accounts SET current_balance = COALESCE(current_balance, 0) + ? WHERE id = ?",
                        (float(amount), int(target_bank_account_id)),
                    )
                    cls._post_finance_transaction(
                        conn=conn,
                        transaction_date=transaction_date,
                        transaction_type="TRANSFER_IN",
                        account_type="BANK",
                        cash_account_id=None,
                        bank_account_id=int(target_bank_account_id),
                        customer_id=None,
                        supplier_id=None,
                        currency=currency,
                        debit=float(amount),
                        credit=0.0,
                        reference_no=reference_no,
                        document_no="",
                        description=description or "Transfer In",
                    )

                cls._post_finance_transaction(
                    conn=conn,
                    transaction_date=transaction_date,
                    transaction_type="TRANSFER_OUT",
                    account_type="CASH",
                    cash_account_id=int(source_cash_account_id),
                    bank_account_id=None,
                    customer_id=None,
                    supplier_id=None,
                    currency=currency,
                    debit=0.0,
                    credit=float(amount),
                    reference_no=reference_no,
                    document_no="",
                    description=description or "Transfer Out",
                )

            conn.commit()

    @classmethod
    def _post_finance_transaction(
        cls,
        *,
        conn,
        transaction_date: str,
        transaction_type: str,
        account_type: str,
        cash_account_id: int | None,
        bank_account_id: int | None,
        customer_id: int | None,
        supplier_id: int | None,
        currency: str,
        debit: float,
        credit: float,
        reference_no: str,
        document_no: str,
        description: str,
    ) -> None:
        tx_no = cls._next_no("finance_transactions", "transaction_no", "FTX")
        conn.execute(
            """
            INSERT INTO finance_transactions(
                transaction_no, transaction_date, transaction_type, account_type,
                cash_account_id, bank_account_id, customer_id, supplier_id,
                currency, debit, credit, reference_no, document_no, description
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                tx_no,
                transaction_date,
                transaction_type,
                account_type,
                cash_account_id,
                bank_account_id,
                customer_id,
                supplier_id,
                currency,
                float(debit or 0),
                float(credit or 0),
                reference_no,
                document_no,
                description,
            ),
        )

    @classmethod
    def list_bank_transactions(cls, keyword: str = "") -> list[dict[str, Any]]:
        params: list[Any] = []
        where = ""
        if keyword.strip():
            token = f"%{keyword.strip().lower()}%"
            where = """
            WHERE LOWER(COALESCE(ft.transaction_no, '')) LIKE ?
               OR LOWER(COALESCE(ba.bank_name, '')) LIKE ?
               OR LOWER(COALESCE(ca.cash_name, '')) LIKE ?
               OR LOWER(COALESCE(ft.description, '')) LIKE ?
               OR LOWER(COALESCE(ft.reference_no, '')) LIKE ?
               OR LOWER(COALESCE(ft.document_no, '')) LIKE ?
            """
            params = [token, token, token, token, token, token]

        with cls._connect() as conn:
            cur = conn.cursor()
            cls._begin_transaction(conn)
            cur.execute(
                f"""
                SELECT
                    ft.id,
                    ft.transaction_date,
                    ft.transaction_no,
                    COALESCE(ba.bank_name, ca.cash_name, '-') AS account_name,
                    COALESCE(ft.description, '') AS description,
                    ft.currency,
                    COALESCE(ft.debit, 0) AS debit,
                    COALESCE(ft.credit, 0) AS credit,
                    COALESCE(ft.reference_no, '') AS reference_no,
                    COALESCE(ft.document_no, '') AS document_no
                FROM finance_transactions ft
                LEFT JOIN bank_accounts ba ON ba.id = ft.bank_account_id
                LEFT JOIN cash_accounts ca ON ca.id = ft.cash_account_id
                {where}
                ORDER BY ft.transaction_date, ft.id
                """,
                params,
            )
            rows = cls._rows_to_dicts(cur.fetchall())

        running = 0.0
        for row in rows:
            running += float(row.get("debit") or 0) - float(row.get("credit") or 0)
            row["running_balance"] = running
        return rows

    @classmethod
    def list_customers(cls) -> list[dict[str, Any]]:
        with cls._connect() as conn:
            cur = conn.cursor()
            cls._begin_transaction(conn)
            cur.execute(
                """
                SELECT id, COALESCE(cari_kodu, '') AS code, COALESCE(firma_unvani, '') AS name
                FROM cariler
                ORDER BY firma_unvani
                """
            )
            rows = cls._rows_to_dicts(cur.fetchall())
        for row in rows:
            cid = int(row.get("id") or 0)
            row["currency"] = cls.customer_account_currency(cid)
            row["balance"] = cls.customer_balance(cid)
        return rows

    @classmethod
    def list_suppliers(cls) -> list[dict[str, Any]]:
        with cls._connect() as conn:
            cur = conn.cursor()
            cls._begin_transaction(conn)
            cur.execute(
                """
                SELECT id, COALESCE(supplier_code, '') AS code, COALESCE(company_name, '') AS name
                FROM suppliers
                ORDER BY company_name
                """
            )
            return cls._rows_to_dicts(cur.fetchall())

    @classmethod
    def list_cari_parties(cls) -> list[dict[str, Any]]:
        parties: list[dict[str, Any]] = []
        with cls._connect() as conn:
            cur = conn.cursor()
            cls._begin_transaction(conn)
            cur.execute(
                """
                SELECT id, COALESCE(cari_kodu, '') AS code, COALESCE(firma_unvani, '') AS name
                FROM cariler
                ORDER BY firma_unvani
                """
            )
            for row in cur.fetchall():
                parties.append(
                    {
                        "party_type": "CUSTOMER",
                        "party_id": int(row["id"] or 0),
                        "code": str(row["code"] or ""),
                        "name": str(row["name"] or ""),
                    }
                )

            cur.execute(
                """
                SELECT id, COALESCE(supplier_code, '') AS code, COALESCE(company_name, '') AS name
                FROM suppliers
                ORDER BY company_name
                """
            )
            for row in cur.fetchall():
                parties.append(
                    {
                        "party_type": "SUPPLIER",
                        "party_id": int(row["id"] or 0),
                        "code": str(row["code"] or ""),
                        "name": str(row["name"] or ""),
                    }
                )

        parties.sort(key=lambda x: (str(x.get("name") or "").lower(), str(x.get("code") or "").lower()))
        return parties

    @classmethod
    def _resolve_default_cash_account_id(cls, *, conn, currency: str) -> int:
        curr = str(currency or "USD").strip().upper() or "USD"
        cur = conn.cursor()
        cur.execute(
            "SELECT id FROM cash_accounts WHERE currency = ? ORDER BY id LIMIT 1",
            (curr,),
        )
        row = cur.fetchone()
        if row is not None:
            return int(row["id"] or 0)

        code = f"KASA-{curr}"
        name = f"Main Cash {curr}"
        cur.execute(
            """
            INSERT INTO cash_accounts(
                cash_code, cash_name, currency, opening_balance, current_balance, opening_date, notes
            ) VALUES(?,?,?,?,?,?,?)
            """,
            (code, name, curr, 0.0, 0.0, cls._now_date(), "Auto-created default cash account"),
        )
        return int(cur.lastrowid)

    @classmethod
    def create_cash_transaction(
        cls,
        *,
        transaction_date: str,
        party_type: str,
        party_id: int,
        transaction_type: str,
        amount: float,
        currency: str,
        description: str,
        cash_account_id: int | None = None,
        exchange_rate: float | None = None,
        voucher_no_override: str | None = None,
    ) -> dict[str, Any]:
        tx_type = str(transaction_type or "").strip().upper()
        if tx_type not in {"INCOME", "EXPENSE"}:
            raise ValueError("Transaction type must be Income or Expense")
        if float(amount or 0) <= 0:
            raise ValueError("Amount must be greater than 0")

        ptype = str(party_type or "").strip().upper()
        if ptype not in {"CUSTOMER", "SUPPLIER"}:
            raise ValueError("Customer/Supplier selection is required")
        pid = int(party_id or 0)
        if pid <= 0:
            raise ValueError("Customer/Supplier selection is required")

        tx_date = str(transaction_date or cls._now_date()).strip() or cls._now_date()
        curr = str(currency or "USD").strip().upper() or "USD"
        desc = str(description or "").strip()
        voucher_no = str(voucher_no_override or "").strip() or cls._next_no("cash_transactions", "voucher_no", "CSV")

        customer_id = pid if ptype == "CUSTOMER" else None
        supplier_id = pid if ptype == "SUPPLIER" else None
        delta = float(amount) if tx_type == "INCOME" else -float(amount)

        with cls._connect() as conn:
            cur = conn.cursor()
            cls._begin_transaction(conn)
            selected_cash_id = int(cash_account_id or 0)
            if selected_cash_id > 0:
                cur.execute(
                    "SELECT id, COALESCE(cash_name, ''), COALESCE(currency, 'USD') FROM cash_accounts WHERE id = ?",
                    (selected_cash_id,),
                )
                selected_cash_row = cur.fetchone()
                if selected_cash_row is None:
                    raise ValueError("Selected cash account was not found")
                selected_cash_currency = str(selected_cash_row[2] or "USD").strip().upper() or "USD"
                if selected_cash_currency != curr:
                    raise ValueError(
                        f"Kasa para birimi ({selected_cash_currency}) ile işlem para birimi ({curr}) aynı olmalıdır."
                    )
                cash_account_id = int(selected_cash_row[0] or 0)
                cash_name = str(selected_cash_row[1] or "")
            else:
                cash_account_id = cls._resolve_default_cash_account_id(conn=conn, currency=curr)
                cur.execute("SELECT COALESCE(cash_name, '') FROM cash_accounts WHERE id = ?", (cash_account_id,))
                name_row = cur.fetchone()
                cash_name = str((name_row[0] if name_row else "") or "")

            ledger_currency = curr
            converted_amount = float(amount)
            effective_rate = 1.0
            if customer_id:
                ledger_currency = cls.customer_account_currency(int(customer_id), conn=conn)
                converted_amount, effective_rate = cls._convert_amount_for_account(
                    amount=float(amount),
                    voucher_currency=curr,
                    account_currency=ledger_currency,
                    exchange_rate=exchange_rate,
                )
            elif supplier_id:
                ledger_currency = cls.supplier_account_currency(int(supplier_id), conn=conn)
                converted_amount, effective_rate = cls._convert_amount_for_account(
                    amount=float(amount),
                    voucher_currency=curr,
                    account_currency=ledger_currency,
                    exchange_rate=exchange_rate,
                )

            cur.execute(
                "UPDATE cash_accounts SET current_balance = COALESCE(current_balance, 0) + ? WHERE id = ?",
                (delta, cash_account_id),
            )
            cur.execute("SELECT COALESCE(current_balance, 0) FROM cash_accounts WHERE id = ?", (cash_account_id,))
            balance_row = cur.fetchone()
            balance_after = float(balance_row[0] or 0)

            cur.execute(
                """
                INSERT INTO cash_transactions(
                    voucher_no, transaction_date, party_type, party_id, customer_id, supplier_id,
                    transaction_type, amount, currency, description, cash_account_id, balance_after, updated_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)
                """,
                (
                    voucher_no,
                    tx_date,
                    ptype,
                    pid,
                    customer_id,
                    supplier_id,
                    tx_type,
                    float(amount),
                    curr,
                    desc,
                    cash_account_id,
                    balance_after,
                ),
            )

            cls._post_finance_transaction(
                conn=conn,
                transaction_date=tx_date,
                transaction_type=f"CASH_{tx_type}",
                account_type="CASH",
                cash_account_id=int(cash_account_id),
                bank_account_id=None,
                customer_id=customer_id,
                supplier_id=supplier_id,
                currency=curr,
                debit=float(amount) if tx_type == "INCOME" else 0.0,
                credit=float(amount) if tx_type == "EXPENSE" else 0.0,
                reference_no=voucher_no,
                document_no="",
                description=desc or f"Cash {tx_type.title()} {voucher_no}",
            )

            if customer_id:
                conversion_note = (
                    ""
                    if curr == ledger_currency
                    else f" | Orijinal: {float(amount):,.2f} {curr} | Kur: {effective_rate:,.6f}"
                )
                movement_desc = "Kasa Tahsilatı" if tx_type == "INCOME" else "Kasa Tediyesi"
                ledger_desc = f"{movement_desc} - {desc}" if desc else f"{movement_desc} {voucher_no}"
                AccountingPostingService.post_customer_ledger(
                    conn=conn,
                    customer_id=int(customer_id),
                    movement_date=tx_date,
                    document_type=movement_desc,
                    reference_type="CASH_TXN",
                    reference_no=voucher_no,
                    debit=float(converted_amount) if tx_type == "INCOME" else 0.0,
                    credit=float(converted_amount) if tx_type == "EXPENSE" else 0.0,
                    currency=ledger_currency,
                    exchange_rate=float(effective_rate),
                    description=ledger_desc + conversion_note,
                    status="Posted",
                )

            if supplier_id:
                supplier_amount = float(converted_amount) if tx_type == "INCOME" else -float(converted_amount)
                conversion_note = (
                    ""
                    if curr == ledger_currency
                    else f" | Orijinal: {float(amount):,.2f} {curr} | Kur: {effective_rate:,.6f}"
                )
                cur.execute(
                    """
                    INSERT INTO supplier_account_movements(
                        supplier_id, movement_date, movement_type, reference_type, reference_no, amount,
                        currency, exchange_rate, description, status
                    ) VALUES(?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        int(supplier_id),
                        tx_date,
                        f"Cash {tx_type.title()}",
                        "CASH_TXN",
                        voucher_no,
                        supplier_amount,
                        ledger_currency,
                        float(effective_rate),
                        (desc or f"Cash {tx_type.title()} {voucher_no}") + conversion_note,
                        "Posted",
                    ),
                )

            conn.commit()
        cls._notify("cash-voucher")

        return {
            "voucher_no": voucher_no,
            "transaction_date": tx_date,
            "transaction_type": tx_type,
            "amount": float(amount),
            "currency": curr,
            "description": desc,
            "cash_account_id": int(cash_account_id),
            "cash_account_name": cash_name,
            "balance_after": balance_after,
            "ledger_currency": ledger_currency,
            "ledger_amount": float(converted_amount),
            "exchange_rate": float(effective_rate),
            "party_type": ptype,
            "party_id": pid,
            "customer_id": customer_id,
            "supplier_id": supplier_id,
        }

    @classmethod
    def create_bank_transaction(
        cls,
        *,
        transaction_date: str,
        bank_account_id: int,
        transfer_type: str,
        party_type: str,
        party_id: int,
        amount: float,
        currency: str,
        description: str,
        exchange_rate: float | None = None,
        voucher_no_override: str | None = None,
    ) -> dict[str, Any]:
        b_id = int(bank_account_id or 0)
        if b_id <= 0:
            raise ValueError("Bank selection is required")

        tr_type = str(transfer_type or "").strip().upper()
        if tr_type not in {"INCOMING", "OUTGOING"}:
            raise ValueError("Transfer type must be Incoming or Outgoing")
        if float(amount or 0) <= 0:
            raise ValueError("Amount must be greater than 0")

        ptype = str(party_type or "").strip().upper()
        if ptype not in {"CUSTOMER", "SUPPLIER"}:
            raise ValueError("Customer/Supplier selection is required")
        pid = int(party_id or 0)
        if pid <= 0:
            raise ValueError("Customer/Supplier selection is required")

        tx_date = str(transaction_date or cls._now_date()).strip() or cls._now_date()
        curr = str(currency or "USD").strip().upper() or "USD"
        desc = str(description or "").strip()
        voucher_no = str(voucher_no_override or "").strip() or cls._next_no("bank_transactions", "voucher_no", "BNK")

        customer_id = pid if ptype == "CUSTOMER" else None
        supplier_id = pid if ptype == "SUPPLIER" else None
        delta = float(amount) if tr_type == "INCOMING" else -float(amount)

        with cls._connect() as conn:
            cur = conn.cursor()
            cur.execute("SELECT COALESCE(currency, 'USD') FROM bank_accounts WHERE id = ?", (b_id,))
            bank_currency_row = cur.fetchone()
            if bank_currency_row is None:
                raise ValueError("Selected bank was not found")
            bank_currency = str(bank_currency_row[0] or "USD").strip().upper() or "USD"
            if bank_currency != curr:
                raise ValueError(
                    f"Banka para birimi ({bank_currency}) ile işlem para birimi ({curr}) aynı olmalıdır."
                )

            ledger_currency = curr
            converted_amount = float(amount)
            effective_rate = 1.0
            if customer_id:
                ledger_currency = cls.customer_account_currency(int(customer_id), conn=conn)
                converted_amount, effective_rate = cls._convert_amount_for_account(
                    amount=float(amount),
                    voucher_currency=curr,
                    account_currency=ledger_currency,
                    exchange_rate=exchange_rate,
                )
            elif supplier_id:
                ledger_currency = cls.supplier_account_currency(int(supplier_id), conn=conn)
                converted_amount, effective_rate = cls._convert_amount_for_account(
                    amount=float(amount),
                    voucher_currency=curr,
                    account_currency=ledger_currency,
                    exchange_rate=exchange_rate,
                )

            cur.execute(
                "UPDATE bank_accounts SET current_balance = COALESCE(current_balance, 0) + ? WHERE id = ?",
                (delta, b_id),
            )
            cur.execute("SELECT COALESCE(current_balance, 0), COALESCE(bank_name, '') FROM bank_accounts WHERE id = ?", (b_id,))
            balance_row = cur.fetchone()
            if balance_row is None:
                raise ValueError("Selected bank was not found")
            balance_after = float(balance_row[0] or 0)
            bank_name = str(balance_row[1] or "")

            cur.execute(
                """
                INSERT INTO bank_transactions(
                    voucher_no, transaction_date, bank_account_id, party_type, party_id, customer_id, supplier_id,
                    transfer_type, amount, currency, description, balance_after, updated_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)
                """,
                (
                    voucher_no,
                    tx_date,
                    b_id,
                    ptype,
                    pid,
                    customer_id,
                    supplier_id,
                    tr_type,
                    float(amount),
                    curr,
                    desc,
                    balance_after,
                ),
            )

            cls._post_finance_transaction(
                conn=conn,
                transaction_date=tx_date,
                transaction_type=f"BANK_{tr_type}",
                account_type="BANK",
                cash_account_id=None,
                bank_account_id=b_id,
                customer_id=customer_id,
                supplier_id=supplier_id,
                currency=curr,
                debit=float(amount) if tr_type == "INCOMING" else 0.0,
                credit=float(amount) if tr_type == "OUTGOING" else 0.0,
                reference_no=voucher_no,
                document_no="",
                description=desc or f"Bank {tr_type.title()} {voucher_no}",
            )

            if customer_id:
                conversion_note = (
                    ""
                    if curr == ledger_currency
                    else f" | Orijinal: {float(amount):,.2f} {curr} | Kur: {effective_rate:,.6f}"
                )
                movement_desc = "Banka Tahsilatı" if tr_type == "INCOMING" else "Banka Tediyesi"
                ledger_desc = f"{movement_desc} - {desc}" if desc else f"{movement_desc} {voucher_no}"
                AccountingPostingService.post_customer_ledger(
                    conn=conn,
                    customer_id=int(customer_id),
                    movement_date=tx_date,
                    document_type=movement_desc,
                    reference_type="BANK_TXN",
                    reference_no=voucher_no,
                    debit=float(converted_amount) if tr_type == "INCOMING" else 0.0,
                    credit=float(converted_amount) if tr_type == "OUTGOING" else 0.0,
                    currency=ledger_currency,
                    exchange_rate=float(effective_rate),
                    description=ledger_desc + conversion_note,
                    status="Posted",
                )

            if supplier_id:
                supplier_amount = float(converted_amount) if tr_type == "INCOMING" else -float(converted_amount)
                conversion_note = (
                    ""
                    if curr == ledger_currency
                    else f" | Orijinal: {float(amount):,.2f} {curr} | Kur: {effective_rate:,.6f}"
                )
                cur.execute(
                    """
                    INSERT INTO supplier_account_movements(
                        supplier_id, movement_date, movement_type, reference_type, reference_no, amount,
                        currency, exchange_rate, description, status
                    ) VALUES(?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        int(supplier_id),
                        tx_date,
                        f"Bank {tr_type.title()}",
                        "BANK_TXN",
                        voucher_no,
                        supplier_amount,
                        ledger_currency,
                        float(effective_rate),
                        (desc or f"Bank {tr_type.title()} {voucher_no}") + conversion_note,
                        "Posted",
                    ),
                )

            conn.commit()
        cls._notify("bank-voucher")

        return {
            "voucher_no": voucher_no,
            "transaction_date": tx_date,
            "transfer_type": tr_type,
            "amount": float(amount),
            "currency": curr,
            "description": desc,
            "bank_account_id": b_id,
            "bank_name": bank_name,
            "balance_after": balance_after,
            "ledger_currency": ledger_currency,
            "ledger_amount": float(converted_amount),
            "exchange_rate": float(effective_rate),
            "party_type": ptype,
            "party_id": pid,
            "customer_id": customer_id,
            "supplier_id": supplier_id,
        }

    @classmethod
    def list_today_cash_transactions(cls, tx_date: str | None = None) -> list[dict[str, Any]]:
        date_value = str(tx_date or cls._now_date()).strip() or cls._now_date()
        with cls._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT
                    ct.transaction_date,
                    ct.voucher_no,
                    COALESCE(c.firma_unvani, s.company_name, '') AS customer_name,
                    COALESCE(ct.description, '') AS description,
                    COALESCE(ct.transaction_type, '') AS transaction_type,
                    COALESCE(ct.amount, 0) AS amount,
                    COALESCE(ct.currency, 'USD') AS currency,
                    COALESCE(ct.updated_at, '') AS updated_at,
                    COALESCE(ct.cash_account_id, 0) AS cash_account_id,
                    COALESCE(ct.party_type, '') AS party_type,
                    COALESCE(ct.party_id, 0) AS party_id
                FROM cash_transactions ct
                LEFT JOIN cariler c ON c.id = ct.customer_id
                LEFT JOIN suppliers s ON s.id = ct.supplier_id
                WHERE ct.transaction_date = ?
                ORDER BY ct.id DESC
                """,
                (date_value,),
            )
            rows = cls._rows_to_dicts(cur.fetchall())

        for row in rows:
            txt = str(row.get("transaction_type") or "").strip().upper()
            row["direction_text"] = "Tahsilat" if txt == "INCOME" else "Tediye"
            row["user"] = "SYSTEM"
            row["status"] = "Posted"
        return rows

    @classmethod
    def list_today_bank_transactions(cls, tx_date: str | None = None) -> list[dict[str, Any]]:
        date_value = str(tx_date or cls._now_date()).strip() or cls._now_date()
        with cls._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT
                    bt.transaction_date,
                    bt.voucher_no,
                    COALESCE(c.firma_unvani, s.company_name, '') AS customer_name,
                    COALESCE(bt.description, '') AS description,
                    COALESCE(bt.transfer_type, '') AS transfer_type,
                    COALESCE(bt.amount, 0) AS amount,
                    COALESCE(bt.currency, 'USD') AS currency,
                    COALESCE(bt.updated_at, '') AS updated_at,
                    COALESCE(bt.bank_account_id, 0) AS bank_account_id,
                    COALESCE(bt.party_type, '') AS party_type,
                    COALESCE(bt.party_id, 0) AS party_id
                FROM bank_transactions bt
                LEFT JOIN cariler c ON c.id = bt.customer_id
                LEFT JOIN suppliers s ON s.id = bt.supplier_id
                WHERE bt.transaction_date = ?
                ORDER BY bt.id DESC
                """,
                (date_value,),
            )
            rows = cls._rows_to_dicts(cur.fetchall())

        for row in rows:
            txt = str(row.get("transfer_type") or "").strip().upper()
            row["direction_text"] = "Tahsilat" if txt == "INCOMING" else "Tediye"
            row["user"] = "SYSTEM"
            row["status"] = "Posted"
        return rows

    @classmethod
    def get_cash_transaction(cls, voucher_no: str) -> dict[str, Any] | None:
        key = str(voucher_no or "").strip()
        if not key:
            return None
        with cls._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT
                    voucher_no, transaction_date, party_type, party_id, customer_id, supplier_id,
                    transaction_type, amount, currency, description, cash_account_id, balance_after
                FROM cash_transactions
                WHERE voucher_no = ?
                LIMIT 1
                """,
                (key,),
            )
            row = cur.fetchone()
            return dict(row) if row is not None else None

    @classmethod
    def get_bank_transaction(cls, voucher_no: str) -> dict[str, Any] | None:
        key = str(voucher_no or "").strip()
        if not key:
            return None
        with cls._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT
                    voucher_no, transaction_date, bank_account_id, party_type, party_id, customer_id, supplier_id,
                    transfer_type, amount, currency, description, balance_after
                FROM bank_transactions
                WHERE voucher_no = ?
                LIMIT 1
                """,
                (key,),
            )
            row = cur.fetchone()
            return dict(row) if row is not None else None

    @classmethod
    def update_cash_transaction(
        cls,
        *,
        voucher_no: str,
        transaction_date: str,
        party_type: str,
        party_id: int,
        transaction_type: str,
        amount: float,
        currency: str,
        description: str,
        cash_account_id: int,
        exchange_rate: float | None = None,
    ) -> dict[str, Any]:
        key = str(voucher_no or "").strip()
        existing = cls.get_cash_transaction(key)
        if existing is None:
            raise ValueError("Düzenlenecek kasa fişi bulunamadı.")

        with cls._connect() as conn:
            cur = conn.cursor()
            old_amount = float(existing.get("amount") or 0)
            old_type = str(existing.get("transaction_type") or "").strip().upper()
            old_delta = old_amount if old_type == "INCOME" else -old_amount
            old_cash_id = int(existing.get("cash_account_id") or 0)
            if old_cash_id > 0:
                cur.execute(
                    "UPDATE cash_accounts SET current_balance = COALESCE(current_balance, 0) - ? WHERE id = ?",
                    (old_delta, old_cash_id),
                )
            cur.execute("DELETE FROM finance_transactions WHERE reference_no = ? AND transaction_type LIKE 'CASH_%'", (key,))
            cur.execute("DELETE FROM customer_account_movements WHERE reference_no = ? AND reference_type = 'CASH_TXN'", (key,))
            cur.execute("DELETE FROM supplier_account_movements WHERE reference_no = ? AND reference_type = 'CASH_TXN'", (key,))
            cur.execute("DELETE FROM cash_transactions WHERE voucher_no = ?", (key,))
            conn.commit()

        result = cls.create_cash_transaction(
            transaction_date=transaction_date,
            party_type=party_type,
            party_id=party_id,
            transaction_type=transaction_type,
            amount=amount,
            currency=currency,
            description=description,
            cash_account_id=cash_account_id,
            exchange_rate=exchange_rate,
            voucher_no_override=key,
        )
        cls._notify("cash-voucher")
        return result

    @classmethod
    def update_bank_transaction(
        cls,
        *,
        voucher_no: str,
        transaction_date: str,
        bank_account_id: int,
        transfer_type: str,
        party_type: str,
        party_id: int,
        amount: float,
        currency: str,
        description: str,
        exchange_rate: float | None = None,
    ) -> dict[str, Any]:
        key = str(voucher_no or "").strip()
        existing = cls.get_bank_transaction(key)
        if existing is None:
            raise ValueError("Düzenlenecek banka fişi bulunamadı.")

        with cls._connect() as conn:
            cur = conn.cursor()
            old_amount = float(existing.get("amount") or 0)
            old_type = str(existing.get("transfer_type") or "").strip().upper()
            old_delta = old_amount if old_type == "INCOMING" else -old_amount
            old_bank_id = int(existing.get("bank_account_id") or 0)
            if old_bank_id > 0:
                cur.execute(
                    "UPDATE bank_accounts SET current_balance = COALESCE(current_balance, 0) - ? WHERE id = ?",
                    (old_delta, old_bank_id),
                )
            cur.execute("DELETE FROM finance_transactions WHERE reference_no = ? AND transaction_type LIKE 'BANK_%'", (key,))
            cur.execute("DELETE FROM customer_account_movements WHERE reference_no = ? AND reference_type = 'BANK_TXN'", (key,))
            cur.execute("DELETE FROM supplier_account_movements WHERE reference_no = ? AND reference_type = 'BANK_TXN'", (key,))
            cur.execute("DELETE FROM bank_transactions WHERE voucher_no = ?", (key,))
            conn.commit()

        result = cls.create_bank_transaction(
            transaction_date=transaction_date,
            bank_account_id=bank_account_id,
            transfer_type=transfer_type,
            party_type=party_type,
            party_id=party_id,
            amount=amount,
            currency=currency,
            description=description,
            exchange_rate=exchange_rate,
            voucher_no_override=key,
        )
        cls._notify("bank-voucher")
        return result

    @classmethod
    def delete_cash_transaction(cls, voucher_no: str) -> None:
        key = str(voucher_no or "").strip()
        if not key:
            raise ValueError("Silinecek kasa fişi bulunamadı.")

        with cls._connect() as conn:
            cls._begin_transaction(conn)
            cur = conn.cursor()
            cur.execute(
                """
                SELECT cash_account_id, transaction_type, amount
                FROM cash_transactions
                WHERE voucher_no = ?
                LIMIT 1
                """,
                (key,),
            )
            row = cur.fetchone()
            if row is None:
                conn.rollback()
                raise ValueError("Silinecek kasa fişi bulunamadı.")

            cash_id = int(row[0] or 0)
            tx_type = str(row[1] or "").strip().upper()
            amount = float(row[2] or 0)
            delta = amount if tx_type == "INCOME" else -amount

            if cash_id > 0:
                cur.execute(
                    "UPDATE cash_accounts SET current_balance = COALESCE(current_balance, 0) - ? WHERE id = ?",
                    (delta, cash_id),
                )

            cur.execute("DELETE FROM finance_transactions WHERE reference_no = ? AND transaction_type LIKE 'CASH_%'", (key,))
            cur.execute("DELETE FROM customer_account_movements WHERE reference_no = ? AND reference_type = 'CASH_TXN'", (key,))
            cur.execute("DELETE FROM supplier_account_movements WHERE reference_no = ? AND reference_type = 'CASH_TXN'", (key,))
            cur.execute("DELETE FROM cash_transactions WHERE voucher_no = ?", (key,))
            conn.commit()

        cls._notify("cash-voucher")

    @classmethod
    def delete_bank_transaction(cls, voucher_no: str) -> None:
        key = str(voucher_no or "").strip()
        if not key:
            raise ValueError("Silinecek banka fişi bulunamadı.")

        with cls._connect() as conn:
            cls._begin_transaction(conn)
            cur = conn.cursor()
            cur.execute(
                """
                SELECT bank_account_id, transfer_type, amount
                FROM bank_transactions
                WHERE voucher_no = ?
                LIMIT 1
                """,
                (key,),
            )
            row = cur.fetchone()
            if row is None:
                conn.rollback()
                raise ValueError("Silinecek banka fişi bulunamadı.")

            bank_id = int(row[0] or 0)
            tr_type = str(row[1] or "").strip().upper()
            amount = float(row[2] or 0)
            delta = amount if tr_type == "INCOMING" else -amount

            if bank_id > 0:
                cur.execute(
                    "UPDATE bank_accounts SET current_balance = COALESCE(current_balance, 0) - ? WHERE id = ?",
                    (delta, bank_id),
                )

            cur.execute("DELETE FROM finance_transactions WHERE reference_no = ? AND transaction_type LIKE 'BANK_%'", (key,))
            cur.execute("DELETE FROM customer_account_movements WHERE reference_no = ? AND reference_type = 'BANK_TXN'", (key,))
            cur.execute("DELETE FROM supplier_account_movements WHERE reference_no = ? AND reference_type = 'BANK_TXN'", (key,))
            cur.execute("DELETE FROM bank_transactions WHERE voucher_no = ?", (key,))
            conn.commit()

        cls._notify("bank-voucher")

    @classmethod
    def list_customer_collections(cls, keyword: str = "") -> list[dict[str, Any]]:
        params: list[Any] = []
        where = ""
        if keyword.strip():
            token = f"%{keyword.strip().lower()}%"
            where = """
            WHERE LOWER(COALESCE(cc.collection_no, '')) LIKE ?
               OR LOWER(COALESCE(c.firma_unvani, '')) LIKE ?
               OR LOWER(COALESCE(cc.invoice_number, '')) LIKE ?
               OR LOWER(COALESCE(cc.reference_no, '')) LIKE ?
            """
            params = [token, token, token, token]

        with cls._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                f"""
                SELECT
                    cc.id,
                    cc.collection_date,
                    cc.collection_no,
                    COALESCE(c.firma_unvani, '') AS customer_name,
                    COALESCE(cc.invoice_number, '') AS invoice_number,
                    COALESCE(cc.amount, 0) AS amount,
                    cc.currency,
                    COALESCE(cc.payment_method, '') AS payment_method,
                    COALESCE(cc.reference_no, '') AS reference_no,
                    COALESCE(ba.bank_name, ca.cash_name, '') AS bank_or_cash,
                    COALESCE(cc.notes, '') AS notes,
                    cc.customer_id,
                    cc.cash_account_id,
                    cc.bank_account_id
                FROM customer_collections cc
                LEFT JOIN cariler c ON c.id = cc.customer_id
                LEFT JOIN bank_accounts ba ON ba.id = cc.bank_account_id
                LEFT JOIN cash_accounts ca ON ca.id = cc.cash_account_id
                {where}
                ORDER BY cc.collection_date DESC, cc.id DESC
                """,
                params,
            )
            return cls._rows_to_dicts(cur.fetchall())

    @classmethod
    def create_customer_collection(
        cls,
        *,
        customer_id: int,
        invoice_number: str,
        amount: float,
        currency: str,
        collection_date: str,
        payment_method: str,
        reference_no: str,
        bank_account_id: int | None,
        cash_account_id: int | None,
        notes: str,
        exchange_rate: float | None = None,
    ) -> int:
        if amount <= 0:
            raise ValueError("Amount must be greater than 0")
        if int(customer_id or 0) <= 0:
            raise ValueError("Customer is required")

        collection_no = cls._next_no("customer_collections", "collection_no", "COL")

        with cls._connect() as conn:
            cur = conn.cursor()

            voucher_currency = str(currency or "USD").strip().upper() or "USD"
            ledger_currency = cls.customer_account_currency(int(customer_id), conn=conn)
            converted_amount, effective_rate = cls._convert_amount_for_account(
                amount=float(amount),
                voucher_currency=voucher_currency,
                account_currency=ledger_currency,
                exchange_rate=exchange_rate,
            )

            cur.execute(
                """
                INSERT INTO customer_collections(
                    collection_no, customer_id, invoice_number, amount, currency, collection_date,
                    payment_method, cash_account_id, bank_account_id, reference_no, notes
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    collection_no,
                    int(customer_id),
                    str(invoice_number or "").strip(),
                    float(amount),
                    voucher_currency,
                    str(collection_date or cls._now_date()),
                    str(payment_method or "BANK").strip() or "BANK",
                    int(cash_account_id) if cash_account_id else None,
                    int(bank_account_id) if bank_account_id else None,
                    str(reference_no or "").strip(),
                    str(notes or "").strip(),
                ),
            )
            new_id = int(cur.lastrowid)

            if bank_account_id:
                cur.execute("SELECT COALESCE(currency, 'USD') FROM bank_accounts WHERE id = ?", (int(bank_account_id),))
                bank_row = cur.fetchone()
                if bank_row is None:
                    raise ValueError("Selected bank was not found")
                bank_currency = str(bank_row[0] or "USD").strip().upper() or "USD"
                if bank_currency != voucher_currency:
                    raise ValueError(
                        f"Banka para birimi ({bank_currency}) ile tahsilat para birimi ({voucher_currency}) aynı olmalıdır."
                    )
                cur.execute("UPDATE bank_accounts SET current_balance = COALESCE(current_balance, 0) + ? WHERE id = ?", (float(amount), int(bank_account_id)))
            if cash_account_id:
                cur.execute("SELECT COALESCE(currency, 'USD') FROM cash_accounts WHERE id = ?", (int(cash_account_id),))
                cash_row = cur.fetchone()
                if cash_row is None:
                    raise ValueError("Selected cash account was not found")
                cash_currency = str(cash_row[0] or "USD").strip().upper() or "USD"
                if cash_currency != voucher_currency:
                    raise ValueError(
                        f"Kasa para birimi ({cash_currency}) ile tahsilat para birimi ({voucher_currency}) aynı olmalıdır."
                    )
                cur.execute("UPDATE cash_accounts SET current_balance = COALESCE(current_balance, 0) + ? WHERE id = ?", (float(amount), int(cash_account_id)))

            pay_label = "Banka Tahsilatı" if str(payment_method or "").strip().upper() == "BANK" else "Kasa Tahsilatı"
            AccountingPostingService.post_customer_ledger(
                conn=conn,
                customer_id=int(customer_id),
                movement_date=str(collection_date or cls._now_date()),
                document_type=pay_label,
                reference_type="COLLECTION",
                reference_no=collection_no,
                debit=float(converted_amount),
                credit=0.0,
                currency=ledger_currency,
                exchange_rate=float(effective_rate),
                description=(
                    f"{pay_label} - {collection_no}"
                    + (
                        ""
                        if voucher_currency == ledger_currency
                        else f" | Orijinal: {float(amount):,.2f} {voucher_currency} | Kur: {effective_rate:,.6f}"
                    )
                ),
                status="Posted",
            )

            cls._post_finance_transaction(
                conn=conn,
                transaction_date=str(collection_date or cls._now_date()),
                transaction_type="COLLECTION",
                account_type="BANK" if bank_account_id else "CASH",
                cash_account_id=int(cash_account_id) if cash_account_id else None,
                bank_account_id=int(bank_account_id) if bank_account_id else None,
                customer_id=int(customer_id),
                supplier_id=None,
                currency=voucher_currency,
                debit=float(amount),
                credit=0.0,
                reference_no=str(reference_no or "").strip(),
                document_no=str(invoice_number or "").strip(),
                description=f"Customer collection {collection_no}",
            )

            conn.commit()
            cls._notify("collection")
            return new_id

    @classmethod
    def delete_customer_collection(cls, collection_id: int) -> None:
        with cls._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT id, collection_no, amount, bank_account_id, cash_account_id
                FROM customer_collections
                WHERE id = ?
                """,
                (int(collection_id),),
            )
            row = cur.fetchone()
            if row is None:
                return

            amount = float(row["amount"] or 0)
            bank_id = row["bank_account_id"]
            cash_id = row["cash_account_id"]
            col_no = str(row["collection_no"] or "")

            if bank_id:
                cur.execute("UPDATE bank_accounts SET current_balance = COALESCE(current_balance, 0) - ? WHERE id = ?", (amount, int(bank_id)))
            if cash_id:
                cur.execute("UPDATE cash_accounts SET current_balance = COALESCE(current_balance, 0) - ? WHERE id = ?", (amount, int(cash_id)))

            cur.execute("DELETE FROM finance_transactions WHERE transaction_type = 'COLLECTION' AND reference_no = ?", (col_no,))
            cur.execute("DELETE FROM customer_account_movements WHERE reference_type = 'COLLECTION' AND reference_no = ?", (col_no,))
            cur.execute("DELETE FROM customer_collections WHERE id = ?", (int(collection_id),))
            conn.commit()
        cls._notify("collection")

    @classmethod
    def list_supplier_payments(cls, keyword: str = "") -> list[dict[str, Any]]:
        params: list[Any] = []
        where = ""
        if keyword.strip():
            token = f"%{keyword.strip().lower()}%"
            where = """
            WHERE LOWER(COALESCE(sp.payment_no, '')) LIKE ?
               OR LOWER(COALESCE(s.company_name, '')) LIKE ?
               OR LOWER(COALESCE(sp.purchase_invoice_number, '')) LIKE ?
               OR LOWER(COALESCE(sp.reference_no, '')) LIKE ?
            """
            params = [token, token, token, token]

        with cls._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                f"""
                SELECT
                    sp.id,
                    sp.payment_date,
                    sp.payment_no,
                    COALESCE(s.company_name, '') AS supplier_name,
                    COALESCE(sp.purchase_invoice_number, '') AS purchase_invoice_number,
                    COALESCE(sp.amount, 0) AS amount,
                    sp.currency,
                    COALESCE(sp.payment_method, '') AS payment_method,
                    COALESCE(sp.reference_no, '') AS reference_no,
                    COALESCE(ba.bank_name, ca.cash_name, '') AS bank_or_cash,
                    COALESCE(sp.notes, '') AS notes,
                    sp.supplier_id,
                    sp.cash_account_id,
                    sp.bank_account_id
                FROM supplier_payments sp
                LEFT JOIN suppliers s ON s.id = sp.supplier_id
                LEFT JOIN bank_accounts ba ON ba.id = sp.bank_account_id
                LEFT JOIN cash_accounts ca ON ca.id = sp.cash_account_id
                {where}
                ORDER BY sp.payment_date DESC, sp.id DESC
                """,
                params,
            )
            return cls._rows_to_dicts(cur.fetchall())

    @classmethod
    def create_supplier_payment(
        cls,
        *,
        supplier_id: int,
        purchase_invoice_number: str,
        amount: float,
        currency: str,
        payment_date: str,
        payment_method: str,
        reference_no: str,
        bank_account_id: int | None,
        cash_account_id: int | None,
        notes: str,
        exchange_rate: float | None = None,
    ) -> int:
        if amount <= 0:
            raise ValueError("Amount must be greater than 0")
        if int(supplier_id or 0) <= 0:
            raise ValueError("Supplier is required")

        payment_no = cls._next_no("supplier_payments", "payment_no", "PAY")

        with cls._connect() as conn:
            cur = conn.cursor()

            voucher_currency = str(currency or "USD").strip().upper() or "USD"
            ledger_currency = cls.supplier_account_currency(int(supplier_id), conn=conn)
            converted_amount, effective_rate = cls._convert_amount_for_account(
                amount=float(amount),
                voucher_currency=voucher_currency,
                account_currency=ledger_currency,
                exchange_rate=exchange_rate,
            )

            cur.execute(
                """
                INSERT INTO supplier_payments(
                    payment_no, supplier_id, purchase_invoice_number, amount, currency, payment_date,
                    payment_method, cash_account_id, bank_account_id, reference_no, notes
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    payment_no,
                    int(supplier_id),
                    str(purchase_invoice_number or "").strip(),
                    float(amount),
                    voucher_currency,
                    str(payment_date or cls._now_date()),
                    str(payment_method or "BANK").strip() or "BANK",
                    int(cash_account_id) if cash_account_id else None,
                    int(bank_account_id) if bank_account_id else None,
                    str(reference_no or "").strip(),
                    str(notes or "").strip(),
                ),
            )
            new_id = int(cur.lastrowid)

            if bank_account_id:
                cur.execute("SELECT COALESCE(currency, 'USD') FROM bank_accounts WHERE id = ?", (int(bank_account_id),))
                bank_row = cur.fetchone()
                if bank_row is None:
                    raise ValueError("Selected bank was not found")
                bank_currency = str(bank_row[0] or "USD").strip().upper() or "USD"
                if bank_currency != voucher_currency:
                    raise ValueError(
                        f"Banka para birimi ({bank_currency}) ile ödeme para birimi ({voucher_currency}) aynı olmalıdır."
                    )
                cur.execute("UPDATE bank_accounts SET current_balance = COALESCE(current_balance, 0) - ? WHERE id = ?", (float(amount), int(bank_account_id)))
            if cash_account_id:
                cur.execute("SELECT COALESCE(currency, 'USD') FROM cash_accounts WHERE id = ?", (int(cash_account_id),))
                cash_row = cur.fetchone()
                if cash_row is None:
                    raise ValueError("Selected cash account was not found")
                cash_currency = str(cash_row[0] or "USD").strip().upper() or "USD"
                if cash_currency != voucher_currency:
                    raise ValueError(
                        f"Kasa para birimi ({cash_currency}) ile ödeme para birimi ({voucher_currency}) aynı olmalıdır."
                    )
                cur.execute("UPDATE cash_accounts SET current_balance = COALESCE(current_balance, 0) - ? WHERE id = ?", (float(amount), int(cash_account_id)))

            cur.execute(
                """
                INSERT INTO supplier_account_movements(
                    supplier_id, movement_date, movement_type, reference_type, reference_no, amount,
                    currency, exchange_rate, description, status
                ) VALUES(?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    int(supplier_id),
                    str(payment_date or cls._now_date()),
                    "Payment",
                    "PAYMENT",
                    payment_no,
                    -float(converted_amount),
                    ledger_currency,
                    float(effective_rate),
                    (
                        f"Supplier payment {payment_no}"
                        + (
                            ""
                            if voucher_currency == ledger_currency
                            else f" | Orijinal: {float(amount):,.2f} {voucher_currency} | Kur: {effective_rate:,.6f}"
                        )
                    ),
                    "Posted",
                ),
            )

            cls._post_finance_transaction(
                conn=conn,
                transaction_date=str(payment_date or cls._now_date()),
                transaction_type="PAYMENT",
                account_type="BANK" if bank_account_id else "CASH",
                cash_account_id=int(cash_account_id) if cash_account_id else None,
                bank_account_id=int(bank_account_id) if bank_account_id else None,
                customer_id=None,
                supplier_id=int(supplier_id),
                currency=voucher_currency,
                debit=0.0,
                credit=float(amount),
                reference_no=str(reference_no or "").strip(),
                document_no=str(purchase_invoice_number or "").strip(),
                description=f"Supplier payment {payment_no}",
            )

            conn.commit()
            cls._notify("payment")
            return new_id

    @classmethod
    def delete_supplier_payment(cls, payment_id: int) -> None:
        with cls._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT id, payment_no, amount, bank_account_id, cash_account_id
                FROM supplier_payments
                WHERE id = ?
                """,
                (int(payment_id),),
            )
            row = cur.fetchone()
            if row is None:
                return

            amount = float(row["amount"] or 0)
            bank_id = row["bank_account_id"]
            cash_id = row["cash_account_id"]
            pay_no = str(row["payment_no"] or "")

            if bank_id:
                cur.execute("UPDATE bank_accounts SET current_balance = COALESCE(current_balance, 0) + ? WHERE id = ?", (amount, int(bank_id)))
            if cash_id:
                cur.execute("UPDATE cash_accounts SET current_balance = COALESCE(current_balance, 0) + ? WHERE id = ?", (amount, int(cash_id)))

            cur.execute("DELETE FROM finance_transactions WHERE transaction_type = 'PAYMENT' AND reference_no = ?", (pay_no,))
            cur.execute("DELETE FROM supplier_account_movements WHERE movement_type = 'Payment' AND reference_no = ?", (pay_no,))
            cur.execute("DELETE FROM supplier_payments WHERE id = ?", (int(payment_id),))
            conn.commit()
        cls._notify("payment")

    @classmethod
    def customer_statement(cls, customer_id: int, *, start_date: str = "", end_date: str = "") -> list[dict[str, Any]]:
        if int(customer_id or 0) <= 0:
            return []

        start = str(start_date or "").strip()
        end = str(end_date or "").strip()

        params: list[Any] = [int(customer_id)]
        where_end = ""
        if end:
            where_end = " AND movement_date <= ?"
            params.append(end)

        with cls._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT movement_date, movement_type, COALESCE(reference_type, '') AS reference_type, COALESCE(reference_no, '') AS reference_no,
                       COALESCE(description, '') AS description, currency, amount
                FROM customer_account_movements
                WHERE customer_id = ?
                """
                + where_end
                +
                """
                ORDER BY movement_date, id
                """,
                params,
            )
            rows = cls._rows_to_dicts(cur.fetchall())

        running = 0.0
        result: list[dict[str, Any]] = []
        type_map = {
            "SALESINVOICE": "Yurtdışı Satış Faturası",
            "PURCHASEINVOICE": "Satın Alma Faturası",
            "PURCHASEORDER": "Satın Alma Siparişi",
            "GOODSRECEIPT": "Mal Kabul",
            "EXPORTSALES": "Yurtdışı Satış",
            "PROFORMA": "Proforma",
            "PACKINGLIST": "Çeki Listesi",
            "CASH_TXN": None,
            "BANK_TXN": None,
            "COLLECTION": None,
        }
        for row in rows:
            movement_date = str(row.get("movement_date") or "")
            amount = float(row.get("amount") or 0)
            running += amount
            if start and movement_date < start:
                continue
            credit = amount if amount > 0 else 0.0
            debit = -amount if amount < 0 else 0.0
            reference_no = str(row.get("reference_no") or "")
            movement_type = str(row.get("movement_type") or "")
            reference_type = str(row.get("reference_type") or "").strip().upper()

            display_type = type_map.get(reference_type)
            if display_type is None:
                normalized = movement_type.strip().lower()
                display_type = movement_type if movement_type else normalized.title()

            raw_desc = str(row.get("description") or "").strip()
            display_desc = raw_desc
            if reference_type == "SALESINVOICE":
                display_desc = f"Yurtdışı Satış Faturası {reference_no}".strip()
            elif reference_type == "PROFORMA":
                display_desc = f"Proforma {reference_no}".strip()
            elif reference_type == "PACKINGLIST":
                display_desc = f"Packing List {reference_no}".strip()
            elif not display_desc:
                display_desc = f"{display_type} {reference_no}".strip()

            result.append(
                {
                    "date": movement_date,
                    "type": display_type,
                    "reference": reference_no,
                    "description": display_desc,
                    "currency": row.get("currency", "USD"),
                    "debit": debit,
                    "credit": credit,
                    "balance": running,
                }
            )
        return result

    @classmethod
    def cash_flow_summary(cls) -> dict[str, float]:
        with cls._connect() as conn:
            cur = conn.cursor()

            cur.execute("SELECT COALESCE(SUM(current_balance), 0) FROM cash_accounts")
            total_cash = float(cur.fetchone()[0] or 0)

            cur.execute("SELECT COALESCE(SUM(current_balance), 0) FROM bank_accounts")
            total_bank = float(cur.fetchone()[0] or 0)

            cur.execute(
                """
                SELECT COALESCE(SUM(CASE WHEN balance > 0 THEN balance ELSE 0 END), 0)
                FROM (
                    SELECT customer_id, COALESCE(SUM(COALESCE(amount, 0)), 0) AS balance
                    FROM customer_account_movements
                    WHERE LOWER(COALESCE(status, '')) != 'cancelled'
                    GROUP BY customer_id
                ) t
                """
            )
            receivables = float(cur.fetchone()[0] or 0)

            cur.execute(
                """
                SELECT COALESCE(SUM(CASE WHEN balance < 0 THEN ABS(balance) ELSE 0 END), 0)
                FROM (
                    SELECT customer_id, COALESCE(SUM(COALESCE(amount, 0)), 0) AS balance
                    FROM customer_account_movements
                    WHERE LOWER(COALESCE(status, '')) != 'cancelled'
                    GROUP BY customer_id
                ) t
                """
            )
            payables = float(cur.fetchone()[0] or 0)

            cur.execute("SELECT COALESCE(SUM(amount), 0) FROM customer_collections WHERE collection_date = ?", (cls._now_date(),))
            today_collections = float(cur.fetchone()[0] or 0)

            cur.execute("SELECT COALESCE(SUM(amount), 0) FROM supplier_payments WHERE payment_date = ?", (cls._now_date(),))
            today_payments = float(cur.fetchone()[0] or 0)

        return {
            "total_cash": total_cash,
            "total_banks": total_bank,
            "today_collections": today_collections,
            "today_payments": today_payments,
            "receivables": receivables,
            "payables": payables,
            "net_cash": total_cash + total_bank,
        }

    @classmethod
    def currency_position(cls) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        currencies = ["TRY", "USD", "EUR"]

        with cls._connect() as conn:
            cur = conn.cursor()
            for code in currencies:
                cur.execute("SELECT COALESCE(SUM(current_balance), 0) FROM cash_accounts WHERE currency = ?", (code,))
                cash = float(cur.fetchone()[0] or 0)

                cur.execute("SELECT COALESCE(SUM(current_balance), 0) FROM bank_accounts WHERE currency = ?", (code,))
                bank = float(cur.fetchone()[0] or 0)

                cur.execute("SELECT COALESCE(SUM(amount), 0) FROM customer_account_movements WHERE currency = ? AND amount > 0", (code,))
                receivable = float(cur.fetchone()[0] or 0)

                cur.execute("SELECT COALESCE(SUM(amount), 0) FROM supplier_account_movements WHERE currency = ? AND amount > 0", (code,))
                payable = float(cur.fetchone()[0] or 0)

                assets = cash + bank + receivable
                liabilities = payable
                net = assets - liabilities

                result.append(
                    {
                        "currency": code,
                        "cash": cash,
                        "bank": bank,
                        "receivable": receivable,
                        "payable": payable,
                        "total_assets": assets,
                        "total_liabilities": liabilities,
                        "net_position": net,
                        "avg_exchange_rate": 1.0,
                        "today_rate": 1.0,
                        "difference": 0.0,
                    }
                )

        return result
