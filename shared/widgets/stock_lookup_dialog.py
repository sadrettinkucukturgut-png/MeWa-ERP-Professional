import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

from PySide6.QtWidgets import QTableWidgetItem

from models.stock_model import StockModel
from shared.widgets.lookup_dialog_base import LookupDialogBase


def _normalize_stock_record(record: Any) -> Optional[Dict[str, Any]]:
    if not record:
        return None

    values = list(record)
    if len(values) < 19:
        return None

    purchase_price = float(values[7] or 0)
    sale_price = float(values[9] or 0)
    current_stock = float(values[13] or 0)

    return {
        "stock_id": int(values[0] or 0),
        "stock_code": str(values[1] or "").strip(),
        "barcode": str(values[2] or "").strip(),
        "product_name": str(values[3] or "").strip(),
        "category": str(values[4] or "").strip(),
        "brand": str(values[5] or "").strip(),
        "unit": str(values[6] or "").strip(),
        "purchase_price": purchase_price,
        "sale_price": sale_price,
        "vat_rate": float(values[11] or 0),
        "current_stock": current_stock,
        "sales_price": sale_price,
        "purchase_price_default": purchase_price,
    }


class StockLookupDialog(LookupDialogBase):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._records: List[Dict[str, Any]] = []
        self.selected_stock: Optional[Dict[str, Any]] = None

        self._build_lookup_shell(
            "Stok Seç",
            "Stok Kodu, Barkod, Ürün Adı, Kategori, Marka veya Birim",
            ["Stok Kodu", "Barkod", "Ürün Adı", "Kategori", "Marka", "Mevcut Stok", "Birim"],
            980,
            580,
        )
        self._load_records()

    def _load_records(self):
        self._records = []
        db_path = Path(StockModel.DB_PATH)
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT
                    id,
                    stock_code,
                    barcode,
                    product_name,
                    category,
                    brand,
                    unit,
                    purchase_price,
                    purchase_currency,
                    sale_price,
                    sale_currency,
                    vat_rate,
                    critical_stock,
                    current_stock,
                    warehouse,
                    shelf,
                    origin,
                    description,
                    image_path
                FROM stoklar
                ORDER BY product_name
                """
            )
            stocks = cursor.fetchall()

        for stock in stocks:
            normalized = _normalize_stock_record(stock)
            if normalized is not None and normalized["stock_code"]:
                self._records.append(normalized)
        self._filter_rows()

    def _filter_rows(self, _text: str = ""):
        keyword = self.search_input.text().strip().lower()
        visible = []
        for record in self._records:
            searchable = " ".join(
                [
                    record["stock_code"],
                    record["barcode"],
                    record["product_name"],
                    record["category"],
                    record["brand"],
                    record["unit"],
                ]
            ).lower()
            if keyword and keyword not in searchable:
                continue
            visible.append(record)

        self._visible_records = visible
        self.table.setRowCount(len(visible))

        for row_index, record in enumerate(visible):
            values = [
                record["stock_code"],
                record["barcode"],
                record["product_name"],
                record["category"],
                record["brand"],
                f"{float(record['current_stock'] or 0):.3f}".rstrip("0").rstrip("."),
                record["unit"],
            ]
            for col_index, value in enumerate(values):
                self.table.setItem(row_index, col_index, QTableWidgetItem(value))

        if visible:
            self.table.selectRow(0)
            self.table.setCurrentCell(0, 0)

    def _accept_first_visible_row(self):
        if self.table.rowCount() == 0:
            return
        self.table.selectRow(0)
        self.table.setCurrentCell(0, 0)
        self._accept_selected()

    def _accept_selected(self):
        row = self.table.currentRow()
        if row < 0 or row >= len(getattr(self, "_visible_records", [])):
            return

        self.selected_stock = dict(self._visible_records[row])
        self.accept()

    @classmethod
    def select_stock(cls, parent=None) -> Optional[Dict[str, Any]]:
        dialog = cls(parent)
        if dialog.exec():
            return dialog.selected_stock
        return None
