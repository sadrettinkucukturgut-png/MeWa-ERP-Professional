from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


class CariHareketleriDialog(QDialog):
    def __init__(self, cari_kodu=None, firma_unvani="", bakiye=0.0, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Cari Hesap Ekstresi")
        self.resize(1100, 700)

        self.cari_kodu = cari_kodu or ""
        self.firma_unvani = firma_unvani or ""
        self.bakiye = bakiye

        self._setup_ui()
        self._load_demo_data()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(16)

        header_frame = QFrame()
        header_frame.setStyleSheet(
            "QFrame{background-color:#f8fafc; border:1px solid #dbe3ec; border-radius:12px;}"
        )
        header_layout = QGridLayout(header_frame)
        header_layout.setContentsMargins(16, 16, 16, 16)
        header_layout.setSpacing(12)

        self.lbl_firma = QLabel(self.firma_unvani or "Firma Ünvanı")
        self.lbl_firma.setStyleSheet("font-size: 20px; font-weight: bold; color: #0f172a;")
        self.lbl_kod = QLabel(f"Cari Kodu: {self.cari_kodu or '-'}")
        self.lbl_kod.setStyleSheet("font-size: 13px; color: #475569;")
        self.lbl_bakiye = QLabel(f"Güncel Bakiye: {self.bakiye:,.2f}")
        self.lbl_bakiye.setStyleSheet("font-size: 15px; font-weight: bold; color: #2563eb;")

        header_layout.addWidget(QLabel("Firma Ünvanı"), 0, 0)
        header_layout.addWidget(self.lbl_firma, 1, 0)
        header_layout.addWidget(QLabel("Cari Kodu"), 0, 1)
        header_layout.addWidget(self.lbl_kod, 1, 1)
        header_layout.addWidget(QLabel("Güncel Bakiye"), 0, 2)
        header_layout.addWidget(self.lbl_bakiye, 1, 2)

        main_layout.addWidget(header_frame)

        self.table = QTableWidget()
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "Tarih",
            "Belge Tipi",
            "Belge No",
            "Açıklama",
            "Borç",
            "Alacak",
            "Bakiye",
        ])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        main_layout.addWidget(self.table)

        bottom_frame = QFrame()
        bottom_frame.setStyleSheet(
            "QFrame{background-color:#f8fafc; border:1px solid #dbe3ec; border-radius:12px;}"
        )
        bottom_layout = QHBoxLayout(bottom_frame)
        bottom_layout.setContentsMargins(16, 16, 16, 16)
        bottom_layout.setSpacing(12)

        self.summary_cards = []
        for title, value in [
            ("Toplam Borç", "0.00"),
            ("Toplam Alacak", "0.00"),
            ("Güncel Bakiye", f"{self.bakiye:,.2f}"),
        ]:
            card = QFrame()
            card.setStyleSheet(
                "QFrame{background-color:white; border:1px solid #e2e8f0; border-radius:12px;}"
            )
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(14, 14, 14, 14)
            card_layout.setSpacing(6)

            value_label = QLabel(value)
            value_label.setStyleSheet("font-size: 20px; font-weight: bold; color: #0f172a;")
            title_label = QLabel(title)
            title_label.setStyleSheet("font-size: 12px; color: #64748b;")

            card_layout.addWidget(value_label)
            card_layout.addWidget(title_label)
            bottom_layout.addWidget(card)
            self.summary_cards.append((title, value_label))

        main_layout.addWidget(bottom_frame)

    def _load_demo_data(self):
        # TODO: Future invoice integration will be added here.
        self.table.setRowCount(3)

        rows = [
            ("2024-01-10", "Fatura", "FAT-001", "Açılış bakiyesi", "1000.00", "0.00", "1000.00"),
            ("2024-01-15", "Tahsilat", "TAH-001", "Ödeme alındı", "0.00", "300.00", "700.00"),
            ("2024-01-20", "Fatura", "FAT-002", "Yeni satış", "500.00", "0.00", "1200.00"),
        ]

        for row_index, row_data in enumerate(rows):
            for column_index, value in enumerate(row_data):
                self.table.setItem(row_index, column_index, QTableWidgetItem(str(value)))

        self._update_summary_cards(rows)

    def _update_summary_cards(self, rows):
        toplam_borç = sum(float(row[4]) for row in rows)
        toplam_alacak = sum(float(row[5]) for row in rows)
        mevcut_bakiye = self.bakiye

        self.summary_cards[0][1].setText(f"{toplam_borç:,.2f}")
        self.summary_cards[1][1].setText(f"{toplam_alacak:,.2f}")
        self.summary_cards[2][1].setText(f"{mevcut_bakiye:,.2f}")

        # TODO: Future invoice integration will be added here.
