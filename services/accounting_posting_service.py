from __future__ import annotations

from typing import Any


class AccountingPostingService:
    """Single posting engine for customer-ledger movements.

    Ledger convention:
    - `amount` keeps signed net effect as (credit - debit)
    - Positive balance => ALACAKLIYIZ
    - Negative balance => BORCLUYUZ
    """

    @staticmethod
    def signed_amount(*, debit: float, credit: float) -> float:
        return float(credit or 0) - float(debit or 0)

    @staticmethod
    def post_customer_ledger(
        *,
        conn,
        customer_id: int,
        movement_date: str,
        document_type: str,
        reference_type: str,
        reference_no: str,
        debit: float,
        credit: float,
        currency: str,
        exchange_rate: float,
        description: str,
        status: str = "Posted",
    ) -> None:
        cid = int(customer_id or 0)
        if cid <= 0:
            raise ValueError("Customer id is required for customer ledger posting")

        conn.execute(
            """
            INSERT INTO customer_account_movements(
                customer_id,
                movement_date,
                movement_type,
                reference_type,
                reference_no,
                amount,
                currency,
                exchange_rate,
                description,
                status
            ) VALUES(?,?,?,?,?,?,?,?,?,?)
            """,
            (
                cid,
                str(movement_date or ""),
                str(document_type or "").strip(),
                str(reference_type or "").strip(),
                str(reference_no or "").strip(),
                AccountingPostingService.signed_amount(debit=float(debit or 0), credit=float(credit or 0)),
                str(currency or "USD").strip().upper() or "USD",
                float(exchange_rate or 1.0),
                str(description or "").strip(),
                str(status or "Posted").strip() or "Posted",
            ),
        )

    @staticmethod
    def resolve_customer_id_for_supplier(*, conn, supplier_id: int) -> int:
        sid = int(supplier_id or 0)
        if sid <= 0:
            return 0

        cur = conn.cursor()
        cur.execute(
            """
            SELECT COALESCE(supplier_code, ''), COALESCE(company_name, '')
            FROM suppliers
            WHERE id = ?
            LIMIT 1
            """,
            (sid,),
        )
        supplier = cur.fetchone()
        if supplier is None:
            return 0

        code = str(supplier[0] or "").strip()
        company = str(supplier[1] or "").strip()

        if code:
            cur.execute(
                "SELECT id FROM cariler WHERE LOWER(COALESCE(cari_kodu, '')) = LOWER(?) LIMIT 1",
                (code,),
            )
            row = cur.fetchone()
            if row is not None:
                return int(row[0] or 0)

        if company:
            cur.execute(
                "SELECT id FROM cariler WHERE LOWER(COALESCE(firma_unvani, '')) = LOWER(?) LIMIT 1",
                (company,),
            )
            row = cur.fetchone()
            if row is not None:
                return int(row[0] or 0)

        return 0

    @staticmethod
    def balance_status(balance: float) -> dict[str, Any]:
        value = float(balance or 0)
        if value > 0:
            return {"code": "ALACAKLIYIZ", "color": "green"}
        if value < 0:
            return {"code": "BORCLUYUZ", "color": "red"}
        return {"code": "BAKIYE YOK", "color": "gray"}
