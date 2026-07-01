import re
import sqlite3
from pathlib import Path

from PySide6.QtCore import QDate, QTime, QTimer, Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QFrame, QGraphicsDropShadowEffect, QGridLayout, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from models.finance_model import FinanceModel
from shared.app_assets import get_company_logo_path, get_scaled_company_logo


class SummaryCard(QFrame):
    def __init__(self, title: str):
        super().__init__()
        self.setObjectName("summaryCard")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setMinimumHeight(110)
        self.setStyleSheet(
            "QFrame#summaryCard{"
            "background-color: rgba(15, 23, 42, 220);"
            "border: 1px solid rgba(100, 116, 139, 120);"
            "border-radius: 12px;"
            "}"
        )

        card_layout = QVBoxLayout(self)
        card_layout.setContentsMargins(14, 12, 14, 12)
        card_layout.setSpacing(6)

        self.value_label = QLabel("0")
        self.value_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.value_label.setStyleSheet("font-size: 28px; font-weight: 700; color: #f8fafc;")

        self.title_label = QLabel(title)
        self.title_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.title_label.setStyleSheet("font-size: 13px; color: #cbd5e1;")

        card_layout.addWidget(self.value_label)
        card_layout.addWidget(self.title_label)

    def set_value(self, value: str) -> None:
        self.value_label.setText(value)


class DashboardPage(QWidget):
    def __init__(self):
        super().__init__()

        self.db_path = Path(__file__).resolve().parent.parent / "database" / "mewa.db"
        self.version_path = Path(__file__).resolve().parent.parent / "docs" / "VERSION.md"
        self.logo_path = get_company_logo_path()
        self.logo_pixmap = QPixmap(str(self.logo_path))

        self._setup_ui()
        self._refresh_summary_cards()
        self._refresh_finance_badge()
        self._update_datetime()

        self._listener = self._on_finance_changed
        FinanceModel.register_listener(self._listener)

        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(self._update_datetime)
        self.clock_timer.start(1000)

    def _setup_ui(self) -> None:
        self.setAttribute(Qt.WA_StyledBackground, True)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 20)
        root.setSpacing(14)

        root.addStretch(2)

        self.logo_label = QLabel()
        self.logo_label.setAlignment(Qt.AlignCenter)
        self.logo_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.logo_label.setMinimumHeight(130)
        self.logo_label.setMaximumHeight(220)
        logo_shadow = QGraphicsDropShadowEffect(self)
        logo_shadow.setBlurRadius(24)
        logo_shadow.setOffset(0, 4)
        logo_shadow.setColor(QColor(0, 0, 0, 120))
        self.logo_label.setGraphicsEffect(logo_shadow)
        root.addWidget(self.logo_label)

        self.main_title_label = QLabel("MeWa ERP Professional")
        self.main_title_label.setAlignment(Qt.AlignCenter)
        self.main_title_label.setStyleSheet("font-size: 34px; font-weight: 700; color: #f8fafc;")
        root.addWidget(self.main_title_label)

        self.sub_title_label = QLabel("Hidrolik Damper Ekipmanları ve Yedek Parçaları")
        self.sub_title_label.setAlignment(Qt.AlignCenter)
        self.sub_title_label.setStyleSheet("font-size: 16px; color: #cbd5e1;")
        root.addWidget(self.sub_title_label)

        self.welcome_label = QLabel("MeWa ERP Professional'a Hoş Geldiniz")
        self.welcome_label.setAlignment(Qt.AlignCenter)
        self.welcome_label.setStyleSheet("font-size: 18px; color: #93c5fd; font-weight: 600;")
        root.addWidget(self.welcome_label)

        root.addStretch(1)

        self.cards_container = QWidget()
        self.cards_grid = QGridLayout(self.cards_container)
        self.cards_grid.setContentsMargins(0, 8, 0, 8)
        self.cards_grid.setHorizontalSpacing(14)
        self.cards_grid.setVerticalSpacing(14)

        self.total_customers_card = SummaryCard("Toplam Cari")
        self.total_suppliers_card = SummaryCard("Toplam Tedarikçi")
        self.total_products_card = SummaryCard("Toplam Ürün")
        self.total_inventory_value_card = SummaryCard("Toplam Stok Değeri")

        self.summary_cards = [
            self.total_customers_card,
            self.total_suppliers_card,
            self.total_products_card,
            self.total_inventory_value_card,
        ]
        self._arrange_cards()

        root.addWidget(self.cards_container)

        self.footer_container = QFrame()
        self.footer_container.setStyleSheet(
            "QFrame{"
            "background-color: rgba(15, 23, 42, 185);"
            "border: 1px solid rgba(100, 116, 139, 110);"
            "border-radius: 10px;"
            "}"
        )
        footer_layout = QHBoxLayout(self.footer_container)
        footer_layout.setContentsMargins(12, 8, 12, 8)
        footer_layout.setSpacing(14)

        self.version_label = QLabel(f"Sürüm: {self._read_version()}")
        self.version_label.setStyleSheet("font-size: 12px; color: #cbd5e1;")
        self.date_label = QLabel("Tarih: -")
        self.date_label.setStyleSheet("font-size: 12px; color: #cbd5e1;")
        self.time_label = QLabel("Saat: -")
        self.time_label.setStyleSheet("font-size: 12px; color: #cbd5e1;")
        self.finance_balance_label = QLabel("Müşteri Bakiye: BAKİYE YOK")
        self.finance_balance_label.setStyleSheet("font-size: 12px; color: #94a3b8; font-weight: 700;")

        footer_layout.addWidget(self.version_label)
        footer_layout.addWidget(self.finance_balance_label)
        footer_layout.addStretch()
        footer_layout.addWidget(self.date_label)
        footer_layout.addWidget(self.time_label)

        root.addWidget(self.footer_container)

        root.addStretch(1)
        self._update_logo()

    def _read_version(self) -> str:
        if not self.version_path.exists():
            return "v0.0.0"

        try:
            content = self.version_path.read_text(encoding="utf-8")
        except OSError:
            return "v0.0.0"

        versions = re.findall(r"^###\s+v(\d+\.\d+\.\d+)", content, flags=re.MULTILINE)
        if not versions:
            return "v0.0.0"
        return f"v{versions[-1]}"

    def _refresh_summary_cards(self) -> None:
        totals = {
            "customers": 0,
            "suppliers": 0,
            "products": 0,
            "inventory_value": 0.0,
        }

        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                cursor.execute("SELECT COUNT(*) FROM cariler")
                totals["customers"] = int(cursor.fetchone()[0] or 0)

                cursor.execute("SELECT COUNT(*) FROM suppliers")
                totals["suppliers"] = int(cursor.fetchone()[0] or 0)

                cursor.execute("SELECT COUNT(*) FROM stoklar")
                totals["products"] = int(cursor.fetchone()[0] or 0)

                cursor.execute("SELECT COALESCE(SUM(COALESCE(current_stock, 0) * COALESCE(sale_price, 0)), 0) FROM stoklar")
                totals["inventory_value"] = float(cursor.fetchone()[0] or 0.0)
        except sqlite3.Error:
            pass

        self.total_customers_card.set_value(str(totals["customers"]))
        self.total_suppliers_card.set_value(str(totals["suppliers"]))
        self.total_products_card.set_value(str(totals["products"]))
        self.total_inventory_value_card.set_value(f"{totals['inventory_value']:,.2f} USD")

    def _refresh_finance_badge(self) -> None:
        summary = FinanceModel.cash_flow_summary()
        receivables = float(summary.get("receivables") or 0)
        payables = float(summary.get("payables") or 0)
        net = receivables - payables
        if net > 0:
            self.finance_balance_label.setText(f"Müşteri Bakiye: {net:,.2f} (ALACAKLIYIZ)")
            self.finance_balance_label.setStyleSheet("font-size: 12px; color: #16a34a; font-weight: 700;")
        elif net < 0:
            self.finance_balance_label.setText(f"Müşteri Bakiye: {abs(net):,.2f} (BORÇLUYUZ)")
            self.finance_balance_label.setStyleSheet("font-size: 12px; color: #dc2626; font-weight: 700;")
        else:
            self.finance_balance_label.setText("Müşteri Bakiye: BAKİYE YOK")
            self.finance_balance_label.setStyleSheet("font-size: 12px; color: #94a3b8; font-weight: 700;")

    def _on_finance_changed(self, _event: str) -> None:
        self._refresh_finance_badge()

    def _update_datetime(self) -> None:
        self.date_label.setText(f"Tarih: {QDate.currentDate().toString('yyyy-MM-dd')}")
        self.time_label.setText(f"Saat: {QTime.currentTime().toString('HH:mm:ss')}")

    def _arrange_cards(self) -> None:
        while self.cards_grid.count():
            item = self.cards_grid.takeAt(0)
            if item.widget() is not None:
                item.widget().setParent(self.cards_container)

        width = max(self.width(), 1)
        if width >= 1400:
            columns = 4
        elif width >= 1024:
            columns = 2
        elif width >= 720:
            columns = 2
        else:
            columns = 1

        for index, card in enumerate(self.summary_cards):
            row = index // columns
            column = index % columns
            self.cards_grid.addWidget(card, row, column)

    def _update_logo(self) -> None:
        if self.logo_pixmap.isNull():
            self.logo_label.setText("MeWa Automotive")
            self.logo_label.setStyleSheet("font-size: 30px; font-weight: 700; color: #f8fafc;")
            return

        available_w = max(220, min(self.width() - 120, 620))
        available_h = max(90, min(self.height() // 4, 210))
        scaled = get_scaled_company_logo(available_w, available_h)
        self.logo_label.setPixmap(scaled)
        self.logo_label.setStyleSheet("")

    def resizeEvent(self, event):  # noqa: N802
        super().resizeEvent(event)
        self._arrange_cards()
        self._update_logo()

    def paintEvent(self, event):  # noqa: N802
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        gradient = QLinearGradient(0, 0, 0, self.height())
        gradient.setStart(0, 0)
        gradient.setFinalStop(0, self.height())
        gradient.setColorAt(0.0, QColor("#0b1220"))
        gradient.setColorAt(0.45, QColor("#111827"))
        gradient.setColorAt(1.0, QColor("#0f172a"))
        painter.fillRect(self.rect(), gradient)

        painter.setPen(Qt.NoPen)

        painter.setBrush(QColor(30, 41, 59, 75))
        path_a = QPainterPath()
        path_a.moveTo(self.width() * 0.00, self.height() * 0.20)
        path_a.lineTo(self.width() * 0.45, self.height() * 0.00)
        path_a.lineTo(self.width() * 0.62, self.height() * 0.18)
        path_a.lineTo(self.width() * 0.20, self.height() * 0.40)
        path_a.closeSubpath()
        painter.drawPath(path_a)

        painter.setBrush(QColor(51, 65, 85, 58))
        path_b = QPainterPath()
        path_b.moveTo(self.width() * 0.40, self.height() * 1.00)
        path_b.lineTo(self.width() * 1.00, self.height() * 0.66)
        path_b.lineTo(self.width() * 1.00, self.height() * 1.00)
        path_b.closeSubpath()
        painter.drawPath(path_b)

        painter.setPen(QPen(QColor(100, 116, 139, 42), 1))
        step = 56
        x = -self.height()
        while x < self.width():
            painter.drawLine(x, self.height(), x + self.height(), 0)
            x += step

    def closeEvent(self, event):  # noqa: N802
        FinanceModel.unregister_listener(self._listener)
        super().closeEvent(event)