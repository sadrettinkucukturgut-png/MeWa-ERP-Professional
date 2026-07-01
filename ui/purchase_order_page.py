from pathlib import Path

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

from models.purchase_order_model import PurchaseOrderModel
from shared.app_assets import get_company_logo_path
from shared.widgets.document_toolbar import DocumentToolbar
from shared.widgets.table_column_state import apply_table_column_standard
from shared.widgets.table_visual import apply_list_table_visuals, create_record_count_label, set_record_count
from ui.new_purchase_order_dialog import NewPurchaseOrderDialog


class PurchaseOrderPage(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Satın Alma Siparişleri")
        self.resize(1280, 720)
        self._all_rows = []
        self._logo_path = self._resolve_logo_path()
        self._setup_ui()
        self.load_purchase_orders()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        self.page_title = QLabel("🧾 Satın Alma Siparişleri")
        self.page_title.setAlignment(Qt.AlignCenter)
        self.page_title.setStyleSheet("font-size:24px; font-weight:bold; padding:8px 0;")
        layout.addWidget(self.page_title)

        search_label = QLabel("Ara:")
        search_label.setStyleSheet("font-weight:bold;")
        layout.addWidget(search_label)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Sipariş No, Tedarikçi, Para Birimi, Durum veya Tarih")
        self.search_input.textChanged.connect(self._handle_search)
        layout.addWidget(self.search_input)

        self.toolbar = QToolBar()
        self.toolbar.setMovable(False)
        layout.addWidget(self.toolbar)

        self.action_new_purchase = QAction("➕ Yeni Satın Alma Siparişi", self)
        self.action_new_purchase.triggered.connect(self._new_purchase_order)
        self.toolbar.addAction(self.action_new_purchase)

        self.action_edit_purchase = QAction("✏️ Düzenle", self)
        self.action_edit_purchase.triggered.connect(self._edit_selected_purchase_order)
        self.toolbar.addAction(self.action_edit_purchase)

        self.action_delete = QAction("🗑 Sil", self)
        self.action_delete.triggered.connect(self._delete_selected_purchase_order)
        self.toolbar.addAction(self.action_delete)

        self.action_delete_purchase = QAction("🛑 İptal", self)
        self.action_delete_purchase.triggered.connect(self._cancel_selected_purchase_order)
        self.toolbar.addAction(self.action_delete_purchase)

        self.toolbar.addSeparator()

        self.toolbar.addSeparator()

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
            ("Toplam Satın Alma Siparişi", "🧾"),
            ("Taslak Sipariş", "📝"),
            ("Onaylı Sipariş", "✅"),
            ("Toplam Alış Tutarı", "💰"),
        ]:
            card = QFrame()
            card.setStyleSheet(
                "QFrame{background-color:#111827; border:1px solid #334155; border-radius:12px;}"
            )
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(14, 14, 14, 14)
            card_layout.setSpacing(6)

            value_label = QLabel("0")
            value_label.setObjectName("statValue")
            value_label.setStyleSheet("font-size:22px; font-weight:bold; color:#f8fafc;")
            title_label = QLabel(f"{icon} {title}")
            title_label.setStyleSheet("font-size:12px; color:#94a3b8;")

            card_layout.addWidget(value_label)
            card_layout.addWidget(title_label)

            self.stats_layout.addWidget(card, 0, len(self.stats_cards))
            self.stats_cards.append((title, value_label))

        self.purchase_table = QTableWidget()
        self.purchase_table.setObjectName("purchaseOrderTable")
        self.column_labels = [
            "Sipariş No",
            "Sipariş Tarihi",
            "Tedarikçi",
            "Para Birimi",
            "Durum",
            "Toplam Tutar",
            "Teslim Tarihi",
            "Oluşturan",
        ]
        self.purchase_table.setColumnCount(len(self.column_labels))
        self.purchase_table.setHorizontalHeaderLabels(self.column_labels)
        self.purchase_table.setAlternatingRowColors(True)
        self.purchase_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.purchase_table.setSelectionMode(QTableWidget.SingleSelection)
        self.purchase_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.purchase_table.setSortingEnabled(True)
        self.purchase_table.verticalHeader().setVisible(False)
        self.purchase_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.purchase_table.customContextMenuRequested.connect(self._show_context_menu)
        self.purchase_table.doubleClicked.connect(self._edit_selected_purchase_order)
        apply_list_table_visuals(self.purchase_table)

        self.settings = QSettings("MeWa", "ERP")
        self._restore_column_visibility()
        apply_table_column_standard(
            self.purchase_table,
            self.settings,
            "purchase_order_table",
            keep_last_column_stretch=False,
        )
        self.document_toolbar = DocumentToolbar(
            parent=self,
            toolbar=self.toolbar,
            table=self.purchase_table,
            settings=self.settings,
            layout_key="purchase_order_table",
            payload_provider=self._document_payload,
        )
        layout.addWidget(self.purchase_table)

        footer_layout = QHBoxLayout()
        footer_layout.addStretch()
        self.record_count_label = create_record_count_label()
        footer_layout.addWidget(self.record_count_label)
        layout.addLayout(footer_layout)

        watermark_layout = QHBoxLayout()
        watermark_layout.setContentsMargins(0, 0, 0, 0)
        watermark_layout.addStretch()
        self.logo_watermark = QLabel()
        self.logo_watermark.setStyleSheet("padding:2px; background:transparent;")
        self.logo_watermark.setAlignment(Qt.AlignRight | Qt.AlignBottom)
        watermark_layout.addWidget(self.logo_watermark)
        layout.addLayout(watermark_layout)
        self._update_logo_watermark()

        self.setStyleSheet(
            self.styleSheet()
            + "QLabel{color:#e2e8f0;} QLineEdit{background:#0f172a; color:#e2e8f0; border:1px solid #334155; border-radius:8px; padding:8px;}"
        )

    def _handle_search(self, text: str):
        self.load_purchase_orders(text)

    def load_purchase_orders(self, filter_text: str = ""):
        records = PurchaseOrderModel.listele(filter_text)
        self._all_rows = records

        was_sorting_enabled = self.purchase_table.isSortingEnabled()
        self.purchase_table.setSortingEnabled(False)
        self.purchase_table.setRowCount(len(records))

        for row_index, row_data in enumerate(records):
            values = [
                row_data.get("order_number", ""),
                row_data.get("order_date", ""),
                row_data.get("supplier_name", ""),
                row_data.get("currency", ""),
                self._status_text(row_data.get("status", "")),
                f"{float(row_data.get('total_amount') or 0):.2f}",
                row_data.get("delivery_date", ""),
                row_data.get("created_by", "SYSTEM"),
            ]
            for column_index, value in enumerate(values):
                self.purchase_table.setItem(
                    row_index,
                    column_index,
                    QTableWidgetItem("" if value is None else str(value)),
                )

        self.purchase_table.setSortingEnabled(was_sorting_enabled)
        set_record_count(self.record_count_label, len(records))
        self._update_statistics(records)

    def _update_statistics(self, records):
        total_orders = len(records)
        draft_orders = sum(1 for row in records if str(row.get("status") or "").strip().lower() == "draft")
        approved_orders = sum(1 for row in records if str(row.get("status") or "").strip().lower() == "approved")
        total_amount = sum(float(row.get("total_amount") or 0) for row in records)

        self.stats_cards[0][1].setText(str(total_orders))
        self.stats_cards[1][1].setText(str(draft_orders))
        self.stats_cards[2][1].setText(str(approved_orders))
        self.stats_cards[3][1].setText(f"{total_amount:,.2f} USD")

    def _new_purchase_order(self):
        dialog = NewPurchaseOrderDialog(parent=self)
        if dialog.exec():
            self.load_purchase_orders(self.search_input.text())

    def _edit_selected_purchase_order(self):
        order_number = self._get_selected_order_number()
        if not order_number:
            return

        dialog = NewPurchaseOrderDialog(order_number=order_number, parent=self)
        if dialog.exec():
            self.load_purchase_orders(self.search_input.text())

    def _cancel_selected_purchase_order(self):
        order_number = self._get_selected_order_number()
        if not order_number:
            return

        answer = QMessageBox.question(
            self,
            "Satın Alma Siparişini İptal Et",
            "Bu işlem siparişi iptal durumuna alır. Devam edilsin mi?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return

        try:
            PurchaseOrderModel.iptal_et(order_number)
            self.load_purchase_orders(self.search_input.text())
        except Exception as exc:
            QMessageBox.critical(self, "Hata", f"İptal işlemi başarısız oldu:\n{exc}")

    def _delete_selected_purchase_order(self):
        order_number = self._get_selected_order_number()
        if not order_number:
            return

        answer = QMessageBox.question(self, "Sil", "Bu kayıt silinsin mi?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if answer != QMessageBox.Yes:
            return
        try:
            PurchaseOrderModel.delete_order(order_number)
            self.load_purchase_orders(self.search_input.text())
        except Exception as exc:
            QMessageBox.warning(self, "Uyarı", str(exc))

    def _show_column_menu(self):
        menu = QMenu(self)
        for index, label in enumerate(self.column_labels):
            action = QAction(label, self)
            action.setCheckable(True)
            action.setChecked(not self.purchase_table.isColumnHidden(index))
            action.triggered.connect(lambda checked, col=index: self._set_column_visibility(col, checked))
            menu.addAction(action)
        menu.exec_(self.toolbar.mapToGlobal(self.toolbar.rect().bottomLeft()))

    def _show_context_menu(self, position):
        row = self.purchase_table.rowAt(position.y())
        if row >= 0:
            self.purchase_table.selectRow(row)

        menu = QMenu(self)
        open_action = QAction("Open", self)
        edit_action = QAction("Düzenle", self)
        delete_action = QAction("Delete", self)
        edit_action.triggered.connect(self._edit_selected_purchase_order)
        open_action.triggered.connect(self._edit_selected_purchase_order)
        delete_action.triggered.connect(self._delete_selected_purchase_order)
        cancel_action = QAction("İptal", self)
        cancel_action.triggered.connect(self._cancel_selected_purchase_order)
        menu.addAction(open_action)
        menu.addAction(edit_action)
        menu.addAction(delete_action)
        menu.addAction(cancel_action)
        menu.exec_(self.purchase_table.viewport().mapToGlobal(position))

    def _get_selected_order_number(self):
        row = self.purchase_table.currentRow()
        if row < 0:
            return None
        item = self.purchase_table.item(row, 0)
        if item is None:
            return None
        value = item.text().strip()
        return value or None

    def _set_column_visibility(self, column_index, visible):
        self.purchase_table.setColumnHidden(column_index, not visible)
        self.settings.setValue(f"purchase_order_columns/{column_index}", visible)

    def _document_payload(self):
        headers = self.column_labels
        rows = []
        for row in range(self.purchase_table.rowCount()):
            values = []
            for col in range(self.purchase_table.columnCount()):
                item = self.purchase_table.item(row, col)
                values.append("" if item is None else item.text())
            rows.append(values)

        selected_row = self.purchase_table.currentRow()
        customer_name = ""
        customer_code = ""
        document_no = self._get_selected_order_number() or ""
        if selected_row >= 0:
            s_item = self.purchase_table.item(selected_row, 2)
            customer_name = "" if s_item is None else s_item.text()

        return {
            "title": "Purchase Order",
            "filename_base": "purchase_order",
            "headers": headers,
            "rows": rows,
            "document_number": document_no,
            "currency": "USD",
            "customer_name": customer_name,
            "customer_code": customer_code,
            "totals": {"Total Amount": self.stats_cards[3][1].text()},
        }

    def _restore_column_visibility(self):
        for index, _ in enumerate(self.column_labels):
            visible = self.settings.value(f"purchase_order_columns/{index}", True)
            self.purchase_table.setColumnHidden(index, not visible)

    def _export_to_excel(self):
        headers = self.column_labels
        rows = []
        for row in range(self.purchase_table.rowCount()):
            values = []
            for col in range(self.purchase_table.columnCount()):
                item = self.purchase_table.item(row, col)
                values.append("" if item is None else item.text())
            rows.append(values)

        ExcelService.export_excel(
            self,
            headers,
            rows,
            "Satin_Alma_Siparisleri.xlsx",
            sheet_title="Satın Alma Siparişleri",
            success_message="Excel dosyası başarıyla export edildi.",
        )

    def _export_to_pdf(self):
        headers = self.column_labels
        rows = []
        for row in range(self.purchase_table.rowCount()):
            values = []
            for col in range(self.purchase_table.columnCount()):
                item = self.purchase_table.item(row, col)
                values.append("" if item is None else item.text())
            rows.append(values)

        PDFService.generate_pdf(
            self,
            headers,
            rows,
            "Satin_Alma_Siparisleri.pdf",
            "Satın Alma Siparişleri",
            logo_path=str(self._logo_path) if self._logo_path.exists() else None,
        )

    def _print_table(self):
        headers = self.column_labels
        rows = []
        for row in range(self.purchase_table.rowCount()):
            values = []
            for col in range(self.purchase_table.columnCount()):
                item = self.purchase_table.item(row, col)
                values.append("" if item is None else item.text())
            rows.append(values)

        PrintService.print_report(self, headers, rows, "Satın Alma Siparişleri")

    def _update_logo_watermark(self):
        width = max(120, min(self.width() // 7, 220))
        height = max(38, min(self.height() // 12, 86))
        if self._logo_path.exists():
            from PySide6.QtGui import QPixmap

            pixmap = QPixmap(str(self._logo_path))
            self.logo_watermark.setPixmap(pixmap.scaled(width, height, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            self.logo_watermark.clear()

    def _resolve_logo_path(self) -> Path:
        return get_company_logo_path()

    @staticmethod
    def _safe_float(value):
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _status_text(status: str) -> str:
        mapping = {
            "draft": "Taslak",
            "approved": "Onaylı",
            "cancelled": "İptal",
            "posted": "İşlenmiş",
        }
        return mapping.get(str(status or "").strip().lower(), str(status or ""))

    def resizeEvent(self, event):  # noqa: N802
        super().resizeEvent(event)
        self._update_logo_watermark()
