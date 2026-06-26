from PySide6.QtWidgets import (
    QDialog,
    QLabel,
    QLineEdit,
    QTextEdit,
    QPushButton,
    QGridLayout,
    QHBoxLayout,
    QVBoxLayout,
    QMessageBox
)

from models.cari_model import CariModel


class NewCariDialog(QDialog):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Yeni Cari Kartı")
        self.resize(700, 500)

        layout = QVBoxLayout(self)

        grid = QGridLayout()

        self.txt_kod = QLineEdit()
        self.txt_unvan = QLineEdit()
        self.txt_yetkili = QLineEdit()
        self.txt_telefon = QLineEdit()
        self.txt_email = QLineEdit()
        self.txt_vergi_dairesi = QLineEdit()
        self.txt_vergi_no = QLineEdit()
        self.txt_ulke = QLineEdit()
        self.txt_sehir = QLineEdit()
        self.txt_adres = QTextEdit()

        grid.addWidget(QLabel("Cari Kodu"), 0, 0)
        grid.addWidget(self.txt_kod, 0, 1)

        grid.addWidget(QLabel("Firma Ünvanı"), 1, 0)
        grid.addWidget(self.txt_unvan, 1, 1)

        grid.addWidget(QLabel("Yetkili"), 2, 0)
        grid.addWidget(self.txt_yetkili, 2, 1)

        grid.addWidget(QLabel("Telefon"), 3, 0)
        grid.addWidget(self.txt_telefon, 3, 1)

        grid.addWidget(QLabel("E-Posta"), 4, 0)
        grid.addWidget(self.txt_email, 4, 1)

        grid.addWidget(QLabel("Vergi Dairesi"), 5, 0)
        grid.addWidget(self.txt_vergi_dairesi, 5, 1)

        grid.addWidget(QLabel("Vergi No"), 6, 0)
        grid.addWidget(self.txt_vergi_no, 6, 1)

        grid.addWidget(QLabel("Ülke"), 7, 0)
        grid.addWidget(self.txt_ulke, 7, 1)

        grid.addWidget(QLabel("Şehir"), 8, 0)
        grid.addWidget(self.txt_sehir, 8, 1)

        grid.addWidget(QLabel("Adres"), 9, 0)
        grid.addWidget(self.txt_adres, 9, 1)

        layout.addLayout(grid)

        buttons = QHBoxLayout()

        self.btn_kaydet = QPushButton("💾 Kaydet")
        self.btn_iptal = QPushButton("İptal")

        buttons.addStretch()
        buttons.addWidget(self.btn_kaydet)
        buttons.addWidget(self.btn_iptal)

        layout.addLayout(buttons)

        self.btn_iptal.clicked.connect(self.close)
        self.btn_kaydet.clicked.connect(self.kaydet)

    def kaydet(self):

        try:

            CariModel.ekle(

                self.txt_kod.text(),
                self.txt_unvan.text(),
                self.txt_yetkili.text(),
                self.txt_telefon.text(),
                self.txt_email.text(),
                self.txt_vergi_dairesi.text(),
                self.txt_vergi_no.text(),
                self.txt_ulke.text(),
                self.txt_sehir.text(),
                self.txt_adres.toPlainText()

            )

            QMessageBox.information(
                self,
                "Başarılı",
                "Cari başarıyla kaydedildi."
            )

            self.accept()

        except Exception as hata:

            QMessageBox.critical(
                self,
                "Hata",
                str(hata)
            )