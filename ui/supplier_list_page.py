import re
import sqlite3
from pathlib import Path

from PySide6.QtCore import Qt, QSettings, QUrl
from PySide6.QtGui import QAction, QDesktopServices
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHeaderView,
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

from services.excel_service import ExcelService
from services.pdf_service import PDFService
from services.print_service import PrintService
from ui.new_supplier_dialog import NewSupplierDialog


class SupplierListPage(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Tedarikçi Listesi")
        self.resize(1200, 650)
        self.db_path = Path(__file__).resolve().parent.parent / "database" / "mewa.db"
        self._setup_ui()
        self.load_supplier_list()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        self.page_title = QLabel("🏭 Tedarikçi Listesi")
        self.page_title.setAlignment(Qt.AlignCenter)
        self.page_title.setStyleSheet("font-size:24px; font-weight:bold; padding:10px 0;")
        layout.addWidget(self.page_title)

        search_label = QLabel("Ara:")
        search_label.setStyleSheet("font-weight:bold;")
        layout.addWidget(search_label)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Tedarikçi Kodu, Firma, Yetkili, Telefon, E-Posta, Şehir veya Ülke")
        self.search_input.textChanged.connect(self._handle_search)
        layout.addWidget(self.search_input)

        self.toolbar = QToolBar()
        self.toolbar.setMovable(False)
        layout.addWidget(self.toolbar)

        self.action_yeni = QAction("➕ Yeni Tedarikçi", self)
        self.action_yeni.triggered.connect(self._yeni_supplier_ekle)
        self.toolbar.addAction(self.action_yeni)

        self.toolbar.addSeparator()

        self.action_excel = QAction("📄 Excel'e Aktar", self)
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
        self.action_whatsapp.triggered.connect(self._open_whatsapp)
        self.toolbar.addAction(self.action_whatsapp)

        self.toolbar.addSeparator()

        self.action_columns = QAction("⚙️ Kolonlar", self)
        self.action_columns.triggered.connect(self._show_column_menu)
        self.toolbar.addAction(self.action_columns)

        self.stats_layout = QGridLayout()
        self.stats_layout.setSpacing(12)
        self.stats_container = QFrame()
        self.stats_container.setStyleSheet("QFrame{background-color:#f5f7fb; border:1px solid #dfe6ee; border-radius:12px;}")
        self.stats_container.setLayout(self.stats_layout)
        layout.addWidget(self.stats_container)

        self.stats_cards = []
        for title, icon in [
            ("Toplam Tedarikçi", "🏭"),
            ("Şehir Sayısı", "🏙"),
            ("Ülke Sayısı", "🌍"),
            ("Varsayılan USD", "💵"),
        ]:
            card = QFrame()
            card.setStyleSheet("QFrame{background-color:white; border:1px solid #e2e8f0; border-radius:12px;}")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(14, 14, 14, 14)
            card_layout.setSpacing(6)

            value_label = QLabel("0")
            value_label.setObjectName("statValue")
            value_label.setStyleSheet("font-size:22px; font-weight:bold; color:#1f2937;")
            title_label = QLabel(f"{icon} {title}")
            title_label.setStyleSheet("font-size:12px; color:#64748b;")

            card_layout.addWidget(value_label)
            card_layout.addWidget(title_label)

            self.stats_layout.addWidget(card, 0, len(self.stats_cards))
            self.stats_cards.append((title, value_label))

        self.supplier_table = QTableWidget()
        self.supplier_table.setObjectName("supplierTable")
        self.column_labels = [
            "Tedarikçi Kodu",
            "Firma Ünvanı",
            "Yetkili Kişi",
            "Telefon",
            "WhatsApp",
            "E-Posta",
            "Şehir",
            "Ülke",
            "Para Birimi",
            "Ödeme Vadesi",
        ]
        self.supplier_table.setColumnCount(len(self.column_labels))
        self.supplier_table.setHorizontalHeaderLabels(self.column_labels)
        self.supplier_table.setAlternatingRowColors(True)
        self.supplier_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.supplier_table.setSelectionMode(QTableWidget.SingleSelection)
        self.supplier_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.supplier_table.setSortingEnabled(False)
        self.supplier_table.verticalHeader().setVisible(False)
        self.supplier_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.supplier_table.doubleClicked.connect(self.supplier_ac)
        self.supplier_table.customContextMenuRequested.connect(self._show_context_menu)
        self.supplier_table.selectionModel().selectionChanged.connect(self._update_whatsapp_action_state)

        header = self.supplier_table.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(QHeaderView.Stretch)

        self.settings = QSettings("MeWa", "ERP")
        self._restore_column_visibility()
        self._update_whatsapp_action_state()
        layout.addWidget(self.supplier_table)

    def load_supplier_list(self, filter_text: str = ""):
        query = """
            SELECT
                supplier_code,
                company_name,
                contact_person,
                phone,
                whatsapp,
                email,
                city,
                country,
                default_currency,
                payment_term
            FROM suppliers
        """

        params = []
        if filter_text.strip():
            keyword = f"%{filter_text.strip()}%"
            query += """
                WHERE
                    LOWER(supplier_code) LIKE ? OR
                    LOWER(company_name) LIKE ? OR
                    LOWER(contact_person) LIKE ? OR
                    LOWER(phone) LIKE ? OR
                    LOWER(whatsapp) LIKE ? OR
                    LOWER(email) LIKE ? OR
                    LOWER(city) LIKE ? OR
                    LOWER(country) LIKE ?
            """
            params = [keyword.lower() for _ in range(8)]

        query += " ORDER BY company_name"

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            veriler = cursor.fetchall()

        self.supplier_table.setRowCount(len(veriler))
        for satir, veri in enumerate(veriler):
            for sutun, deger in enumerate(veri):
                self.supplier_table.setItem(
                    satir,
                    sutun,
                    QTableWidgetItem("" if deger is None else str(deger)),
                )

        self._update_statistics(veriler)

    def _update_statistics(self, veriler):
        toplam_tedarikci = len(veriler)
        sehir_sayisi = len({veri[6] for veri in veriler if veri[6]})
        ulke_sayisi = len({veri[7] for veri in veriler if veri[7]})
        usd_count = sum(1 for veri in veriler if str(veri[8] or "").upper() == "USD")

        self.stats_cards[0][1].setText(str(toplam_tedarikci))
        self.stats_cards[1][1].setText(str(sehir_sayisi))
        self.stats_cards[2][1].setText(str(ulke_sayisi))
        self.stats_cards[3][1].setText(str(usd_count))

    def _handle_search(self, text: str):
        self.load_supplier_list(text)

    def _update_whatsapp_action_state(self):
        selected_row = self.supplier_table.currentRow()
        if selected_row < 0:
            self.action_whatsapp.setEnabled(False)
            return

        phone_item = self.supplier_table.item(selected_row, 4)
        phone_text = phone_item.text().strip() if phone_item is not None else ""
        normalized_phone = self._normalize_phone_number(phone_text)
        self.action_whatsapp.setEnabled(bool(normalized_phone))

    def _normalize_phone_number(self, phone: str) -> str:
        if not phone:
            return ""
        cleaned = re.sub(r"\D", "", phone)
        if not cleaned:
            return ""
        if phone.strip().startswith("+"):
            return "+" + cleaned
        if phone.strip().startswith("00"):
            return "+" + cleaned[2:]
        if cleaned.startswith("90") and len(cleaned) >= 11:
            return "+" + cleaned
        if cleaned.startswith("0") and len(cleaned) >= 10:
            return "+90" + cleaned[1:]
        if len(cleaned) >= 10:
            return "+" + cleaned
        return ""

    def _open_whatsapp(self):
        selected_row = self.supplier_table.currentRow()
        if selected_row < 0:
            return

        phone_item = self.supplier_table.item(selected_row, 4)
        phone_text = phone_item.text().strip() if phone_item is not None else ""
        normalized_phone = self._normalize_phone_number(phone_text)
        if not normalized_phone:
            QMessageBox.warning(self, "Uyarı", "Seçili tedarikçinin telefon numarası bulunamadı.")
            return

        desktop_url = QUrl(f"whatsapp://send?phone={normalized_phone}")
        if QDesktopServices.openUrl(desktop_url):
            return

        web_url = QUrl(f"https://web.whatsapp.com/send?phone={normalized_phone}")
        QDesktopServices.openUrl(web_url)

    def _show_column_menu(self):
        menu = QMenu(self)
        for index, label in enumerate(self.column_labels):
            action = QAction(label, self)
            action.setCheckable(True)
            action.setChecked(not self.supplier_table.isColumnHidden(index))
            action.triggered.connect(lambda checked, col=index: self._set_column_visibility(col, checked))
            menu.addAction(action)
        menu.exec_(self.toolbar.mapToGlobal(self.toolbar.rect().bottomLeft()))

    def _set_column_visibility(self, column_index, visible):
        self.supplier_table.setColumnHidden(column_index, not visible)
        self.settings.setValue(f"supplier_columns/{column_index}", visible)

    def _restore_column_visibility(self):
        for index, _ in enumerate(self.column_labels):
            visible = self.settings.value(f"supplier_columns/{index}", True)
            self.supplier_table.setColumnHidden(index, not visible)

    def _yeni_supplier_ekle(self):
        dialog = NewSupplierDialog()
        if dialog.exec():
            self.load_supplier_list(self.search_input.text())

    def _get_selected_supplier_code(self):
        selected_row = self.supplier_table.currentRow()
        if selected_row < 0:
            return None

        supplier_code_item = self.supplier_table.item(selected_row, 0)
        if supplier_code_item is None:
            return None

        return supplier_code_item.text().strip()

    def _show_context_menu(self, position):
        row = self.supplier_table.rowAt(position.y())
        if row >= 0:
            self.supplier_table.selectRow(row)

        menu = QMenu(self)
        duzenle_action = QAction("Düzenle", self)
        duzenle_action.triggered.connect(self.supplier_ac)
        menu.addAction(duzenle_action)

        sil_action = QAction("Sil", self)
        sil_action.triggered.connect(self._sil_supplier)
        menu.addAction(sil_action)

        menu.exec_(self.supplier_table.viewport().mapToGlobal(position))

    def supplier_ac(self):
        supplier_code = self._get_selected_supplier_code()
        if not supplier_code:
            return

        dialog = NewSupplierDialog(supplier_code)
        if dialog.exec():
            self.load_supplier_list(self.search_input.text())

    def _sil_supplier(self):
        supplier_code = self._get_selected_supplier_code()
        if not supplier_code:
            return

        cevap = QMessageBox.question(self, "Silme Onayı", "Tedarikçi kaydı silinsin mi?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if cevap == QMessageBox.Yes:
            try:
                from models.supplier_model import SupplierModel

                SupplierModel.sil(supplier_code)
                self.load_supplier_list(self.search_input.text())
            except Exception as exc:
                QMessageBox.critical(self, "Hata", f"Tedarikçi silinirken bir hata oluştu:\n{exc}")

    def _export_to_excel(self):
        headers = self.column_labels
        rows = []
        for row in range(self.supplier_table.rowCount()):
            values = []
            for col in range(self.supplier_table.columnCount()):
                item = self.supplier_table.item(row, col)
                values.append("" if item is None else item.text())
            rows.append(values)

        ExcelService.export_excel(
            self,
            headers,
            rows,
            "Tedarikci_Listesi.xlsx",
            sheet_title="Tedarikçi Listesi",
            success_message="Excel dosyası başarıyla export edildi.",
        )

    def _export_to_pdf(self):
        headers = self.column_labels
        rows = []
        for row in range(self.supplier_table.rowCount()):
            values = []
            for col in range(self.supplier_table.columnCount()):
                item = self.supplier_table.item(row, col)
                values.append("" if item is None else item.text())
            rows.append(values)

        PDFService.generate_pdf(self, headers, rows, "Tedarikci_Listesi.pdf", "Tedarikçi Listesi", logo_path=None)

    def _print_table(self):
        headers = self.column_labels
        rows = []
        for row in range(self.supplier_table.rowCount()):
            values = []
            for col in range(self.supplier_table.columnCount()):
                item = self.supplier_table.item(row, col)
                values.append("" if item is None else item.text())
            rows.append(values)

        PrintService.print_report(self, headers, rows, "Tedarikçi Listesi")
