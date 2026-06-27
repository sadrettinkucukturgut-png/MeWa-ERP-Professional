from pathlib import Path
from typing import Any, Dict, List

from PySide6.QtCore import Qt, QSettings
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from models.goods_receipt_model import GoodsReceiptModel
from services.excel_service import ExcelService
from services.pdf_service import PDFService
from services.print_service import PrintService
from shared.app_assets import get_scaled_company_logo
from shared.widgets.table_column_state import add_layout_lock_toggle, apply_table_column_standard
from shared.widgets.table_visual import apply_list_table_visuals, create_record_count_label, set_record_count
from ui.new_goods_receipt_dialog import NewGoodsReceiptDialog


class GoodsReceiptPage(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Mal Kabul")
        self.resize(1280, 720)
        self._logo_path = self._resolve_logo_path()
        self._rows = []
        self._setup_ui()
        self.load_receipts()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        self.page_title = QLabel("📦 Mal Kabul")
        self.page_title.setAlignment(Qt.AlignCenter)
        self.page_title.setStyleSheet("font-size:24px; font-weight:bold; padding:8px 0;")
        layout.addWidget(self.page_title)

        search_label = QLabel("Ara:")
        search_label.setStyleSheet("font-weight:bold;")
        layout.addWidget(search_label)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Fiş No, Sipariş, Tedarikçi, Depo veya Durum")
        self.search_input.textChanged.connect(self._handle_search)
        layout.addWidget(self.search_input)

        self.toolbar = QToolBar()
        self.toolbar.setMovable(False)
        layout.addWidget(self.toolbar)

        self.action_new = QAction("➕ Yeni Mal Kabul", self)
        self.action_new.triggered.connect(self._new_receipt)
        self.toolbar.addAction(self.action_new)

        self.action_edit = QAction("✏️ Düzenle", self)
        self.action_edit.triggered.connect(self._edit_selected)
        self.toolbar.addAction(self.action_edit)

        self.action_cancel = QAction("🛑 İptal", self)
        self.action_cancel.triggered.connect(self._cancel_selected)
        self.toolbar.addAction(self.action_cancel)

        self.toolbar.addSeparator()

        self.action_excel = QAction("📄 Excel", self)
        self.action_excel.triggered.connect(self._export_to_excel)
        self.toolbar.addAction(self.action_excel)

        self.action_pdf = QAction("🖨 PDF", self)
        self.action_pdf.triggered.connect(self._export_to_pdf)
        self.toolbar.addAction(self.action_pdf)

        self.action_print = QAction("🖨 Yazdır", self)
        self.action_print.triggered.connect(self._print_table)
        self.toolbar.addAction(self.action_print)

        self.action_whatsapp = QAction("🟢 WhatsApp", self)
        self.action_whatsapp.setEnabled(False)
        self.toolbar.addAction(self.action_whatsapp)

        self.toolbar.addSeparator()

        self.action_columns = QAction("⚙️ Kolonlar", self)
        self.action_columns.triggered.connect(self._show_column_menu)
        self.toolbar.addAction(self.action_columns)

        self.stats_layout = QGridLayout()
        self.stats_layout.setSpacing(12)
        self.stats_container = QFrame()
        self.stats_container.setStyleSheet(
            "QFrame{background-color:#0f172a; border:1px solid #334155; border-radius:12px;}"
        )
        self.stats_container.setLayout(self.stats_layout)
        layout.addWidget(self.stats_container)

        self.stats_cards = []
        for title, icon in [
            ("Toplam Fiş", "📦"),
            ("İşlenmiş", "✅"),
            ("İptal", "🛑"),
            ("Toplam Miktar", "🔢"),
        ]:
            card = QFrame()
            card.setStyleSheet(
                "QFrame{background-color:#111827; border:1px solid #334155; border-radius:12px;}"
            )
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(14, 14, 14, 14)
            card_layout.setSpacing(6)

            value = QLabel("0")
            value.setObjectName("statValue")
            value.setStyleSheet("font-size:22px; font-weight:bold; color:#f8fafc;")
            label = QLabel(f"{icon} {title}")
            label.setStyleSheet("font-size:12px; color:#94a3b8;")

            card_layout.addWidget(value)
            card_layout.addWidget(label)
            self.stats_layout.addWidget(card, 0, len(self.stats_cards))
            self.stats_cards.append((title, value))

        self.table = QTableWidget()
        self.table.setObjectName("goodsReceiptTable")
        self.column_labels = [
            "Fiş No",
            "Satın Alma Siparişi",
            "Tedarikçi",
            "Fiş Tarihi",
            "Depo",
            "Durum",
            "Toplam Miktar",
            "Oluşturan",
        ]
        self.table.setColumnCount(len(self.column_labels))
        self.table.setHorizontalHeaderLabels(self.column_labels)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSortingEnabled(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        self.table.doubleClicked.connect(self._edit_selected)
        apply_list_table_visuals(self.table)

        self.settings = QSettings("MeWa", "ERP")
        self._restore_column_visibility()
        apply_table_column_standard(
            self.table,
            self.settings,
            "goods_receipt_table",
            keep_last_column_stretch=False,
        )
        self.action_layout_lock = add_layout_lock_toggle(
            self.toolbar,
            self.table,
            self.settings,
            "goods_receipt_table",
            self,
            keep_last_column_stretch=False,
        )

        layout.addWidget(self.table)

        footer = QHBoxLayout()
        footer.addStretch()
        self.record_count_label = create_record_count_label()
        footer.addWidget(self.record_count_label)
        layout.addLayout(footer)

        watermark_layout = QHBoxLayout()
        watermark_layout.addStretch()
        self.logo_watermark = QLabel()
        self.logo_watermark.setAlignment(Qt.AlignRight | Qt.AlignBottom)
        watermark_layout.addWidget(self.logo_watermark)
        layout.addLayout(watermark_layout)
        self._update_logo_watermark()

        self.setStyleSheet(
            self.styleSheet()
            + "QLabel{color:#e2e8f0;} QLineEdit{background:#0f172a; color:#e2e8f0; border:1px solid #334155; border-radius:8px; padding:8px;}"
        )

    def _handle_search(self, text: str):
        self.load_receipts(text)

    def load_receipts(self, keyword: str = ""):
        rows = GoodsReceiptModel.list_receipts(keyword)
        self._rows = rows

        sorting = self.table.isSortingEnabled()
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(rows))

        for row_index, row in enumerate(rows):
            values = [
                row.get("receipt_number", ""),
                row.get("purchase_order", ""),
                row.get("supplier", ""),
                row.get("receipt_date", ""),
                row.get("warehouse", ""),
                self._status_text(row.get("status", "")),
                f"{float(row.get('total_quantity') or 0):.3f}".rstrip("0").rstrip("."),
                row.get("created_by", "SYSTEM"),
            ]
            for col, value in enumerate(values):
                self.table.setItem(row_index, col, QTableWidgetItem("" if value is None else str(value)))

        self.table.setSortingEnabled(sorting)
        set_record_count(self.record_count_label, len(rows))
        self._update_stats(rows)

    def _update_stats(self, rows: List[Dict[str, Any]]):
        total = len(rows)
        posted = sum(1 for row in rows if str(row.get("status") or "").lower() == "posted")
        cancelled = sum(1 for row in rows if str(row.get("status") or "").lower() == "cancelled")
        quantity = sum(float(row.get("total_quantity") or 0) for row in rows)

        self.stats_cards[0][1].setText(str(total))
        self.stats_cards[1][1].setText(str(posted))
        self.stats_cards[2][1].setText(str(cancelled))
        self.stats_cards[3][1].setText(f"{quantity:,.3f}")

    def _new_receipt(self):
        dialog = NewGoodsReceiptDialog(parent=self)
        if dialog.exec():
            self.load_receipts(self.search_input.text())

    def _edit_selected(self):
        receipt_no = self._selected_receipt_no()
        if not receipt_no:
            return

        dialog = NewGoodsReceiptDialog(receipt_number=receipt_no, parent=self)
        if dialog.exec():
            self.load_receipts(self.search_input.text())

    def _cancel_selected(self):
        receipt_no = self._selected_receipt_no()
        if not receipt_no:
            return

        answer = QMessageBox.question(
            self,
            "Mal Kabulü İptal Et",
            "Bu işlem fişi iptal durumuna alır. Devam edilsin mi?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return

        try:
            GoodsReceiptModel.cancel_receipt(receipt_no)
            self.load_receipts(self.search_input.text())
        except Exception as exc:
            QMessageBox.critical(self, "Hata", f"İptal işlemi başarısız oldu:\n{exc}")

    def _show_column_menu(self):
        menu = QMenu(self)
        for index, label in enumerate(self.column_labels):
            action = QAction(label, self)
            action.setCheckable(True)
            action.setChecked(not self.table.isColumnHidden(index))
            action.triggered.connect(lambda checked, col=index: self._set_column_visibility(col, checked))
            menu.addAction(action)
        menu.exec_(self.toolbar.mapToGlobal(self.toolbar.rect().bottomLeft()))

    def _show_context_menu(self, pos):
        row = self.table.rowAt(pos.y())
        if row >= 0:
            self.table.selectRow(row)

        menu = QMenu(self)
        edit_action = QAction("Düzenle", self)
        edit_action.triggered.connect(self._edit_selected)
        cancel_action = QAction("İptal", self)
        cancel_action.triggered.connect(self._cancel_selected)
        menu.addAction(edit_action)
        menu.addAction(cancel_action)
        menu.exec_(self.table.viewport().mapToGlobal(pos))

    def _selected_receipt_no(self):
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        if item is None:
            return None
        value = item.text().strip()
        return value or None

    def _set_column_visibility(self, index: int, visible: bool):
        self.table.setColumnHidden(index, not visible)
        self.settings.setValue(f"goods_receipt_columns/{index}", visible)

    def _restore_column_visibility(self):
        for index, _ in enumerate(self.column_labels):
            visible = self.settings.value(f"goods_receipt_columns/{index}", True)
            self.table.setColumnHidden(index, not visible)

    def _export_to_excel(self):
        headers = self.column_labels
        rows = []
        for row in range(self.table.rowCount()):
            values = []
            for col in range(self.table.columnCount()):
                item = self.table.item(row, col)
                values.append("" if item is None else item.text())
            rows.append(values)

        ExcelService.export_excel(
            self,
            headers,
            rows,
            "Mal_Kabul_Listesi.xlsx",
            sheet_title="Mal Kabul Listesi",
            success_message="Excel dosyası başarıyla export edildi.",
        )

    def _export_to_pdf(self):
        headers = self.column_labels
        rows = []
        for row in range(self.table.rowCount()):
            values = []
            for col in range(self.table.columnCount()):
                item = self.table.item(row, col)
                values.append("" if item is None else item.text())
            rows.append(values)

        PDFService.generate_pdf(
            self,
            headers,
            rows,
            "Mal_Kabul_Listesi.pdf",
            "Mal Kabul Listesi",
            logo_path=str(self._logo_path) if self._logo_path.exists() else None,
        )

    def _print_table(self):
        headers = self.column_labels
        rows = []
        for row in range(self.table.rowCount()):
            values = []
            for col in range(self.table.columnCount()):
                item = self.table.item(row, col)
                values.append("" if item is None else item.text())
            rows.append(values)

        PrintService.print_report(self, headers, rows, "Mal Kabul Listesi")

    def _resolve_logo_path(self) -> Path:
        project_root = Path(__file__).resolve().parent.parent
        official = project_root / "assets" / "logos" / "mewa_logo.png"
        fallback = project_root / "assets" / "logo.png"
        return official if official.exists() else fallback

    def _update_logo_watermark(self):
        width = max(120, min(self.width() // 7, 220))
        height = max(38, min(self.height() // 12, 86))
        self.logo_watermark.setPixmap(get_scaled_company_logo(width, height))

    def resizeEvent(self, event):  # noqa: N802
        super().resizeEvent(event)
        self._update_logo_watermark()

    @staticmethod
    def _status_text(status: str) -> str:
        mapping = {
            "draft": "Taslak",
            "approved": "Onaylı",
            "cancelled": "İptal",
            "posted": "İşlenmiş",
        }
        return mapping.get(str(status or "").strip().lower(), str(status or ""))
