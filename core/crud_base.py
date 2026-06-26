import sqlite3
from typing import Any, Dict, List, Optional, Tuple


class BaseCrud:
    """Generic SQLite CRUD base class for ERP entities."""

    db_path = "database/mewa.db"
    table_name = ""
    id_field = "id"

    def __init__(self, db_path: Optional[str] = None):
        if db_path:
            self.db_path = db_path

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def load_all(self, order_by: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            cursor = conn.cursor()
            query = f"SELECT * FROM {self.table_name}"
            if order_by:
                query += f" ORDER BY {order_by}"
            cursor.execute(query)
            columns = [column[1] for column in cursor.description] if cursor.description else []
            rows = cursor.fetchall()
            return [dict(zip(columns, row)) for row in rows]

    def insert(self, values: Dict[str, Any]) -> int:
        with self._connect() as conn:
            cursor = conn.cursor()
            columns = ", ".join(values.keys())
            placeholders = ", ".join(["?" for _ in values])
            query = f"INSERT INTO {self.table_name} ({columns}) VALUES ({placeholders})"
            cursor.execute(query, tuple(values.values()))
            conn.commit()
            return int(cursor.lastrowid)

    def update(self, record_id: int, values: Dict[str, Any]) -> None:
        if not values:
            return

        with self._connect() as conn:
            cursor = conn.cursor()
            assignments = ", ".join([f"{key} = ?" for key in values.keys()])
            query = f"UPDATE {self.table_name} SET {assignments} WHERE {self.id_field} = ?"
            cursor.execute(query, tuple(values.values()) + (record_id,))
            conn.commit()

    def delete(self, record_id: int) -> None:
        with self._connect() as conn:
            cursor = conn.cursor()
            query = f"DELETE FROM {self.table_name} WHERE {self.id_field} = ?"
            cursor.execute(query, (record_id,))
            conn.commit()

    def find_by_id(self, record_id: int) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            cursor = conn.cursor()
            query = f"SELECT * FROM {self.table_name} WHERE {self.id_field} = ?"
            cursor.execute(query, (record_id,))
            row = cursor.fetchone()
            if row is None:
                return None
            columns = [column[1] for column in cursor.description] if cursor.description else []
            return dict(zip(columns, row))

    def search(self, filters: Optional[Dict[str, Any]] = None, order_by: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            cursor = conn.cursor()
            query = f"SELECT * FROM {self.table_name}"
            params: List[Any] = []

            if filters:
                conditions = []
                for key, value in filters.items():
                    if value is None:
                        continue
                    conditions.append(f"{key} LIKE ?")
                    params.append(f"%{value}%")
                if conditions:
                    query += " WHERE " + " AND ".join(conditions)

            if order_by:
                query += f" ORDER BY {order_by}"

            cursor.execute(query, params)
            columns = [column[1] for column in cursor.description] if cursor.description else []
            rows = cursor.fetchall()
            return [dict(zip(columns, row)) for row in rows]
