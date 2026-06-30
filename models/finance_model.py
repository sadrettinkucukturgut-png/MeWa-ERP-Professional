from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any


class FinanceModel:
    DB_PATH = str(Path(__file__).resolve().parent.parent / "database" / "mewa.db")

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
            cur.execute(
                f"""
                SELECT id, cash_code, cash_name, currency,
                       COALESCE(opening_balance, 0) AS opening_balance,
                       COALESCE(current_balance, 0) AS current_balance,
                       COALESCE(opening_date, '') AS opening_date,
                       COALESCE(notes, '') AS notes
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
                return int(cash_id)

            cur.execute(
                """
                INSERT INTO cash_accounts(cash_code, cash_name, currency, opening_balance, current_balance, opening_date, notes)
                VALUES(?,?,?,?,?,?,?)
                """,
                (code, name, currency, float(opening_balance or 0), float(opening_balance or 0), opening_date, notes),
            )
            conn.commit()
            return int(cur.lastrowid)

    @classmethod
    def delete_cash_account(cls, cash_id: int) -> None:
        with cls._connect() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM cash_accounts WHERE id = ?", (int(cash_id),))
            conn.commit()

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
            cur.execute(
                f"""
                SELECT id, bank_code, bank_name, COALESCE(branch_name, '') AS branch_name,
                       COALESCE(iban, '') AS iban, COALESCE(swift_code, '') AS swift_code,
                       COALESCE(account_number, '') AS account_number,
                       currency,
                       COALESCE(opening_balance, 0) AS opening_balance,
                       COALESCE(current_balance, 0) AS current_balance,
                       COALESCE(opening_date, '') AS opening_date,
                       COALESCE(notes, '') AS notes
                FROM bank_accounts
                {where}
                ORDER BY bank_name
                """,
                params,
            )
            return cls._rows_to_dicts(cur.fetchall())

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
            return int(cur.lastrowid)

    @classmethod
    def delete_bank_account(cls, bank_id: int) -> None:
        with cls._connect() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM bank_accounts WHERE id = ?", (int(bank_id),))
            conn.commit()

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
            cur.execute(
                """
                SELECT id, COALESCE(cari_kodu, '') AS code, COALESCE(firma_unvani, '') AS name
                FROM cariler
                ORDER BY firma_unvani
                """
            )
            return cls._rows_to_dicts(cur.fetchall())

    @classmethod
    def list_suppliers(cls) -> list[dict[str, Any]]:
        with cls._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT id, COALESCE(supplier_code, '') AS code, COALESCE(company_name, '') AS name
                FROM suppliers
                ORDER BY company_name
                """
            )
            return cls._rows_to_dicts(cur.fetchall())

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
    ) -> int:
        if amount <= 0:
            raise ValueError("Amount must be greater than 0")
        if int(customer_id or 0) <= 0:
            raise ValueError("Customer is required")

        collection_no = cls._next_no("customer_collections", "collection_no", "COL")

        with cls._connect() as conn:
            cur = conn.cursor()
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
                    str(currency or "USD").strip() or "USD",
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
                cur.execute("UPDATE bank_accounts SET current_balance = COALESCE(current_balance, 0) + ? WHERE id = ?", (float(amount), int(bank_account_id)))
            if cash_account_id:
                cur.execute("UPDATE cash_accounts SET current_balance = COALESCE(current_balance, 0) + ? WHERE id = ?", (float(amount), int(cash_account_id)))

            cur.execute(
                """
                INSERT INTO customer_account_movements(
                    customer_id, movement_date, movement_type, reference_type, reference_no, amount,
                    currency, exchange_rate, description, status
                ) VALUES(?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    int(customer_id),
                    str(collection_date or cls._now_date()),
                    "Collection",
                    "COLLECTION",
                    collection_no,
                    -float(amount),
                    str(currency or "USD").strip() or "USD",
                    1.0,
                    f"Collection {collection_no}",
                    "Posted",
                ),
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
                currency=str(currency or "USD").strip() or "USD",
                debit=float(amount),
                credit=0.0,
                reference_no=str(reference_no or "").strip(),
                document_no=str(invoice_number or "").strip(),
                description=f"Customer collection {collection_no}",
            )

            conn.commit()
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
            cur.execute("DELETE FROM customer_account_movements WHERE movement_type = 'Collection' AND reference_no = ?", (col_no,))
            cur.execute("DELETE FROM customer_collections WHERE id = ?", (int(collection_id),))
            conn.commit()

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
    ) -> int:
        if amount <= 0:
            raise ValueError("Amount must be greater than 0")
        if int(supplier_id or 0) <= 0:
            raise ValueError("Supplier is required")

        payment_no = cls._next_no("supplier_payments", "payment_no", "PAY")

        with cls._connect() as conn:
            cur = conn.cursor()
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
                    str(currency or "USD").strip() or "USD",
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
                cur.execute("UPDATE bank_accounts SET current_balance = COALESCE(current_balance, 0) - ? WHERE id = ?", (float(amount), int(bank_account_id)))
            if cash_account_id:
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
                    -float(amount),
                    str(currency or "USD").strip() or "USD",
                    1.0,
                    f"Supplier payment {payment_no}",
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
                currency=str(currency or "USD").strip() or "USD",
                debit=0.0,
                credit=float(amount),
                reference_no=str(reference_no or "").strip(),
                document_no=str(purchase_invoice_number or "").strip(),
                description=f"Supplier payment {payment_no}",
            )

            conn.commit()
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

    @classmethod
    def customer_statement(cls, customer_id: int) -> list[dict[str, Any]]:
        with cls._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT movement_date, movement_type, COALESCE(reference_no, '') AS reference_no,
                       COALESCE(description, '') AS description, currency, amount
                FROM customer_account_movements
                WHERE customer_id = ?
                ORDER BY movement_date, id
                """,
                (int(customer_id),),
            )
            rows = cls._rows_to_dicts(cur.fetchall())

        running = 0.0
        result: list[dict[str, Any]] = []
        for row in rows:
            amount = float(row.get("amount") or 0)
            debit = amount if amount > 0 else 0.0
            credit = -amount if amount < 0 else 0.0
            running += amount
            result.append(
                {
                    "date": row.get("movement_date", ""),
                    "type": row.get("movement_type", ""),
                    "reference": row.get("reference_no", ""),
                    "description": row.get("description", ""),
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

            cur.execute("SELECT COALESCE(SUM(amount), 0) FROM customer_account_movements WHERE amount > 0")
            receivables = float(cur.fetchone()[0] or 0)

            cur.execute("SELECT COALESCE(SUM(amount), 0) FROM supplier_account_movements WHERE amount > 0")
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
