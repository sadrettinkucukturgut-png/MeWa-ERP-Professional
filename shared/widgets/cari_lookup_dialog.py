from typing import Any, Dict, List, Optional

from PySide6.QtWidgets import QTableWidgetItem

from models.cari_model import CariModel
from models.supplier_model import SupplierModel
from shared.widgets.lookup_dialog_base import LookupDialogBase


def _normalize_supplier_record(record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    supplier_code = str(record.get("supplier_code") or "").strip()
    company_name = str(record.get("company_name") or "").strip()
    if not supplier_code and not company_name:
        return None

    return {
        "supplier_id": int(record.get("id") or 0),
        "cari_kodu": supplier_code,
        "company_name": company_name,
        "firma_unvani": company_name,
        "contact_person": str(record.get("contact_person") or "").strip(),
        "phone": str(record.get("phone") or "").strip(),
        "tax_number": str(record.get("tax_number") or "").strip(),
        "vergi_no": str(record.get("tax_number") or "").strip(),
        "yetkili": str(record.get("contact_person") or "").strip(),
        "telefon": str(record.get("phone") or "").strip(),
        "city": str(record.get("city") or "").strip(),
        "sehir": str(record.get("city") or "").strip(),
        "country": str(record.get("country") or "").strip(),
        "ulke": str(record.get("country") or "").strip(),
        "cari_tipi": "Tedarikçi",
        "default_currency": str(record.get("default_currency") or "USD").strip() or "USD",
        "payment_term": str(record.get("payment_term") or "").strip(),
    }


class CariLookupDialog(LookupDialogBase):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._records: List[Dict[str, Any]] = []
        self.selected_cari: Optional[Dict[str, Any]] = None

        self._build_lookup_shell(
            "Cari Seç",
            "Cari Kodu, Firma Ünvanı, Telefon, Vergi No, Ülke veya Şehir",
            ["Cari Kodu", "Firma Ünvanı", "Yetkili", "Telefon", "Vergi No", "Şehir", "Ülke", "Cari Tipi"],
            920,
            560,
        )
        self._load_records()

    def _load_records(self):
        try:
            self._records = CariModel.lookup_kayitlari()
        except Exception:
            self._records = []

        if not self._records:
            for record in SupplierModel.tum_tedarikciler():
                normalized = self._normalize_record(record)
                if normalized is not None:
                    self._records.append(normalized)
        self._filter_rows()

    def _normalize_record(self, record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        return _normalize_supplier_record(record)

    def _filter_rows(self, _text: str = ""):
        keyword = self.search_input.text().strip().lower()
        visible = []
        for record in self._records:
            searchable = " ".join(
                [
                    record["cari_kodu"],
                    record["firma_unvani"],
                    record["yetkili"],
                    record["telefon"],
                    str(record.get("vergi_no") or record.get("tax_number") or ""),
                    record["sehir"],
                    record["ulke"],
                    record["cari_tipi"],
                ]
            ).lower()
            if keyword and keyword not in searchable:
                continue
            visible.append(record)

        self._visible_records = visible
        self.table.setRowCount(len(visible))

        for row_index, record in enumerate(visible):
            values = [
                record["cari_kodu"],
                record["firma_unvani"],
                record["yetkili"],
                record["telefon"],
                str(record.get("vergi_no") or record.get("tax_number") or ""),
                record["sehir"],
                record["ulke"],
                record["cari_tipi"],
            ]
            for col_index, value in enumerate(values):
                self.table.setItem(row_index, col_index, QTableWidgetItem(value))

        if visible:
            self.table.selectRow(0)
            self.table.setCurrentCell(0, 0)
            self.table.setFocus()

    def _accept_first_visible_row(self):
        if self.table.rowCount() == 0:
            return
        self._accept_row(0)

    def _accept_selected(self, *_args):
        row = self.table.currentRow()
        if row < 0 or row >= len(getattr(self, "_visible_records", [])):
            return

        self.selected_cari = dict(self._visible_records[row])
        self.accept()

    @classmethod
    def select_cari(cls, parent=None) -> Optional[Dict[str, Any]]:
        dialog = cls(parent)
        if dialog.exec():
            return dialog.selected_cari
        return None

    @classmethod
    def get_cari_by_supplier_id(cls, supplier_id: int) -> Optional[Dict[str, Any]]:
        if supplier_id <= 0:
            return None

        for record in CariModel.tedarikci_lookup_kayitlari():
            if int(record.get("supplier_id") or 0) == supplier_id:
                return dict(record)

        for record in SupplierModel.tum_tedarikciler():
            if int(record.get("id") or 0) == supplier_id:
                return _normalize_supplier_record(record)
        return None
