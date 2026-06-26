from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QTableWidget,
    QTableWidgetItem,
    QLabel
)
from PySide6.QtCore import Qt
import sqlite3


class CariListPage(QWidget):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Cari Listesi")
        self.resize(900, 500)

        layout = QVBoxLayout(self)

        baslik = QLabel("📋 Cari Listesi")
        baslik.setAlignment(Qt.AlignCenter)
        baslik.setStyleSheet("""
            font-size:24px;
            font-weight:bold;
            padding:15px;
        """)

        layout.addWidget(baslik)

        self.table = QTableWidget()

        self.table.setColumnCount(5)

        self.table.setHorizontalHeaderLabels([
            "Cari Kodu",
            "Firma Ünvanı",
            "Yetkili",
            "Telefon",
            "Şehir"
        ])

        layout.addWidget(self.table)

        self.yukle()

    def yukle(self):

        conn = sqlite3.connect("database/mewa.db")

        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                cari_kodu,
                firma_unvani,
                yetkili,
                telefon,
                sehir
            FROM cariler
        """)

        veriler = cursor.fetchall()

        print("Bulunan kayıt sayısı:", len(veriler))
        print(veriler)

        self.table.setRowCount(len(veriler))

        for satir, veri in enumerate(veriler):
            for sutun, deger in enumerate(veri):
                self.table.setItem(
                    satir,
                    sutun,
                    QTableWidgetItem(str(deger))
                )

        conn.close()