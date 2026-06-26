from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QHBoxLayout,
)
from PySide6.QtCore import Qt

from ui.new_cari_dialog import NewCariDialog
from ui.cari_list_page import CariListPage


class CariPage(QWidget):

    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)

        baslik = QLabel("👥 Cari Yönetimi")
        baslik.setAlignment(Qt.AlignCenter)
        baslik.setStyleSheet("""
            font-size:26px;
            font-weight:bold;
            color:white;
            padding:15px;
        """)

        layout.addWidget(baslik)

        ust_menu = QHBoxLayout()

        self.btn_yeni = QPushButton("➕ Yeni Cari")
        self.btn_liste = QPushButton("📋 Cari Listesi")
        self.btn_ekstre = QPushButton("📄 Cari Ekstresi")

        for btn in [self.btn_yeni, self.btn_liste, self.btn_ekstre]:
            btn.setMinimumHeight(40)
            ust_menu.addWidget(btn)

        layout.addLayout(ust_menu)

        bilgi = QLabel("Cari modülü hazırlanıyor...")
        bilgi.setAlignment(Qt.AlignCenter)
        bilgi.setStyleSheet("""
            font-size:18px;
            color:gray;
        """)

        layout.addStretch()
        layout.addWidget(bilgi)
        layout.addStretch()

        # Olaylar
        self.btn_yeni.clicked.connect(self.yeni_cari)
        self.btn_liste.clicked.connect(self.cari_listesi)

    def yeni_cari(self):
        dialog = NewCariDialog()
        dialog.exec()

    def cari_listesi(self):
        self.dialog = CariListPage()
        self.dialog.show()