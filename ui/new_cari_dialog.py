from PySide6.QtWidgets import (
    QDialog,
    QGridLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QMessageBox,
)

from models.cari_model import CariModel


class NewCariDialog(QDialog):
    def __init__(self, cari_kodu=None, parent=None):
        super().__init__(parent)

        self.cari_kodu = cari_kodu
        self.is_edit_mode = cari_kodu is not None

        self.setWindowTitle("Cari Düzenle" if self.is_edit_mode else "Yeni Cari Kartı")
        self.resize(700, 500)

        self.txt_kod = QLineEdit()
        self.txt_unvan = QLineEdit()
        self.txt_yetkili = QLineEdit()
        self.txt_telefon = QLineEdit()
        self.txt_email = QLineEdit()
        self.txt_vergi_dairesi = QLineEdit()
        self.txt_vergi_no = QLineEdit()
        self.txt_ulke = QLineEdit()
        self.txt_sehir = QLineEdit()
        self.txt_ilce = QLineEdit()
        self.txt_adres = QTextEdit()
        self.txt_adres.setMinimumHeight(120)

        self.btn_kaydet = QPushButton("💾 Güncelle" if self.is_edit_mode else "💾 Kaydet")
        self.btn_iptal = QPushButton("İptal")

        self.btn_kaydet.clicked.connect(self._on_save)
        self.btn_iptal.clicked.connect(self.reject)

        grid = QGridLayout()
        grid.setContentsMargins(20, 20, 20, 20)
        grid.setSpacing(12)

        fields = [
            ("Cari Kodu", self.txt_kod),
            ("Firma Ünvanı", self.txt_unvan),
            ("Yetkili", self.txt_yetkili),
            ("Telefon", self.txt_telefon),
            ("E-Posta", self.txt_email),
            ("Vergi Dairesi", self.txt_vergi_dairesi),
            ("Vergi No", self.txt_vergi_no),
            ("Ülke", self.txt_ulke),
            ("Şehir", self.txt_sehir),
            ("İlçe", self.txt_ilce),
        ]

        for index, (label_text, widget) in enumerate(fields):
            label = QLabel(label_text)
            grid.addWidget(label, index, 0)
            grid.addWidget(widget, index, 1)

        grid.addWidget(QLabel("Adres"), len(fields), 0)
        grid.addWidget(self.txt_adres, len(fields), 1, 1, 1)

        button_layout = QVBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(self.btn_kaydet)
        button_layout.addWidget(self.btn_iptal)

        main_layout = QVBoxLayout(self)
        main_layout.addLayout(grid)
        main_layout.addLayout(button_layout)

        if self.is_edit_mode:
            self._load_customer_data()

    def _load_customer_data(self):
        try:
            veri = CariModel.getir(self.cari_kodu)
            if not veri:
                QMessageBox.warning(self, "Bilgi", "Cari bulunamadı.")
                self.reject()
                return

            self.txt_kod.setText(veri[0] or "")
            self.txt_unvan.setText(veri[1] or "")
            self.txt_yetkili.setText(veri[2] or "")
            self.txt_telefon.setText(veri[3] or "")
            self.txt_email.setText(veri[4] or "")
            self.txt_vergi_dairesi.setText(veri[5] or "")
            self.txt_vergi_no.setText(veri[6] or "")
            self.txt_ulke.setText(veri[7] or "")
            self.txt_sehir.setText(veri[8] or "")
            self.txt_ilce.setText(veri[9] or "")
            self.txt_adres.setPlainText(veri[10] or "")
        except Exception as exc:
            QMessageBox.critical(self, "Hata", f"Cari verileri yüklenirken bir hata oluştu:\n{exc}")
            self.reject()

    def _on_save(self):
        cari_kodu = self.txt_kod.text().strip()
        firma_unvani = self.txt_unvan.text().strip()
        yetkili = self.txt_yetkili.text().strip()
        telefon = self.txt_telefon.text().strip()
        email = self.txt_email.text().strip()
        vergi_dairesi = self.txt_vergi_dairesi.text().strip()
        vergi_no = self.txt_vergi_no.text().strip()
        ulke = self.txt_ulke.text().strip()
        sehir = self.txt_sehir.text().strip()
        ilce = self.txt_ilce.text().strip()
        adres = self.txt_adres.toPlainText().strip()

        required_fields = [
            ("Cari Kodu", cari_kodu),
            ("Firma Ünvanı", firma_unvani),
            ("Yetkili", yetkili),
            ("E-Posta", email),
            ("Vergi Dairesi", vergi_dairesi),
            ("Vergi No", vergi_no),
            ("Ülke", ulke),
            ("Şehir", sehir),
            ("İlçe", ilce),
            ("Adres", adres),
        ]

        for field_name, value in required_fields:
            if not value:
                QMessageBox.warning(self, "Eksik Bilgi", f"{field_name} alanı zorunludur.")
                return

        try:
            if self.is_edit_mode:
                CariModel.guncelle(
                    self.cari_kodu,
                    firma_unvani,
                    yetkili,
                    telefon,
                    email,
                    vergi_dairesi,
                    vergi_no,
                    ulke,
                    sehir,
                    ilce,
                    adres,
                )
                QMessageBox.information(self, "Başarılı", "Cari başarıyla güncellendi.")
            else:
                CariModel.ekle(
                    cari_kodu,
                    firma_unvani,
                    yetkili,
                    telefon,
                    email,
                    vergi_dairesi,
                    vergi_no,
                    ulke,
                    sehir,
                    ilce,
                    adres,
                )
                QMessageBox.information(self, "Başarılı", "Cari başarıyla eklendi.")

            self.accept()
        except Exception as exc:
            if self.is_edit_mode:
                QMessageBox.critical(self, "Hata", f"Cari güncellenirken bir hata oluştu:\n{exc}")
            else:
                QMessageBox.critical(self, "Hata", f"Cari eklenirken bir hata oluştu:\n{exc}")