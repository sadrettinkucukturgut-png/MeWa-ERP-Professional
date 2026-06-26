from pathlib import Path
import sqlite3

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QLabel,
    QHeaderView,
    QLineEdit,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


class CariListPage(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Cari Listesi")
        self.resize(900, 500)

        self.db_path = Path(__file__).resolve().parent.parent / "database" / "mewa.db"

        self._setup_ui()
        self.load_cari_list()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        self.page_title = QLabel("📋 Cari Listesi")
        self.page_title.setAlignment(Qt.AlignCenter)
        self.page_title.setStyleSheet(
            ""
            "font-size: 24px;"
            "font-weight: bold;"
            "padding: 10px 0;"
            ""
        )
        layout.addWidget(self.page_title)

        search_label = QLabel("Ara:")
        search_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(search_label)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Cari Kodu, Firma Ünvanı, Yetkili, Telefon veya Şehir")
        self.search_input.textChanged.connect(self._handle_search)
        layout.addWidget(self.search_input)

        self.cari_table = QTableWidget()
        self.cari_table.setObjectName("cariTable")
        self.cari_table.setColumnCount(5)
        self.cari_table.setHorizontalHeaderLabels([
            "Cari Kodu",
            "Firma Ünvanı",
            "Yetkili",
            "Telefon",
            "Şehir",
        ])
        self.cari_table.setAlternatingRowColors(True)
        self.cari_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.cari_table.setSelectionMode(QTableWidget.SingleSelection)
        self.cari_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.cari_table.setSortingEnabled(False)
        self.cari_table.verticalHeader().setVisible(False)
        self.cari_table.doubleClicked.connect(self.cari_ac)

        header = self.cari_table.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(QHeaderView.Stretch)

        layout.addWidget(self.cari_table)

    def load_cari_list(self, filter_text: str = ""):
        query = """
            SELECT
                cari_kodu,
                firma_unvani,
                yetkili,
                telefon,
                sehir
            FROM cariler
        """

        params = []
        if filter_text.strip():
            keyword = f"%{filter_text.strip()}%"
            query += """
                WHERE
                    LOWER(cari_kodu) LIKE ? OR
                    LOWER(firma_unvani) LIKE ? OR
                    LOWER(yetkili) LIKE ? OR
                    LOWER(telefon) LIKE ? OR
                    LOWER(sehir) LIKE ?
            """
            params = [keyword.lower() for _ in range(5)]

        query += " ORDER BY firma_unvani"

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(query, params)
        veriler = cursor.fetchall()
        conn.close()

        self.cari_table.setRowCount(len(veriler))

        for satir, veri in enumerate(veriler):
            for sutun, deger in enumerate(veri):
                self.cari_table.setItem(
                    satir,
                    sutun,
                    QTableWidgetItem("" if deger is None else str(deger)),
                )

    def _handle_search(self, text: str):
        self.load_cari_list(text)

    def cari_ac(self):
        # TODO: Cari kartı detay sayfası eklenecek.
        return