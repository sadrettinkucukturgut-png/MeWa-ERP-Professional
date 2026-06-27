from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QScrollArea,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from core.tab_manager import TabManager
from shared.widgets.menu_button import MenuButton
from ui.cari_list_page import CariListPage
from ui.dashboard_page import DashboardPage
from ui.stock_list_page import StockListPage
from ui.supplier_list_page import SupplierListPage


class PlaceholderPage(QWidget):
    def __init__(self, title: str):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        label = QLabel(f"{title}\n\nYakında eklenecek")
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("font-size: 20px; color: #64748b;")
        layout.addWidget(label)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("MeWa ERP Professional")
        self.resize(1400, 800)

        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.sidebar = QFrame()
        self.sidebar.setFixedWidth(260)
        self.sidebar.setStyleSheet(
            "QFrame{background-color:#0f172a; border:none;}"
        )

        sidebar_scroll = QScrollArea(self.sidebar)
        sidebar_scroll.setWidgetResizable(True)
        sidebar_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        sidebar_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        sidebar_scroll.setFrameShape(QFrame.NoFrame)
        sidebar_scroll.setStyleSheet(
            "QScrollArea{background-color:#0f172a; border:none;}"
            "QScrollBar:vertical{background:#0f172a; width:8px;}"
            "QScrollBar::handle:vertical{background:#475569; border-radius:4px;}"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical{height:0px;}"
        )

        sidebar_content = QWidget()
        sidebar_layout = QVBoxLayout(sidebar_content)
        sidebar_layout.setContentsMargins(12, 12, 12, 12)
        sidebar_layout.setSpacing(8)

        title = QLabel("MeWa ERP")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: white; padding: 8px 4px;")
        sidebar_layout.addWidget(title)

        self.menu_groups = []
        self.group_buttons = {}

        menu_items = [
            ("📊 ANA SAYFA", [("🏠 Dashboard", self.open_dashboard)]),
            (
                "👥 CARİ",
                [
                    ("📋 Cari Kartları", self.open_cari_list),
                    ("📄 Cari Hareketleri", self.open_cari_hareketleri),
                ],
            ),
            (
                "📦 STOK",
                [
                    ("📦 Stok Kartları", self.open_stock_list),
                    ("🗂 Kategoriler", self.open_stock_categories),
                ],
            ),
            (
                "🏭 TEDARİKÇİLER",
                [
                    ("📋 Tedarikçi Kartları", self.open_supplier_list),
                ],
            ),
            (
                "🛒 SATIN ALMA",
                [
                    ("🧾 Siparişler", self.open_purchase_orders),
                    ("🚚 İrsaliyeler", self.open_purchase_delivery_notes),
                    ("🧾 Faturalar", self.open_purchase_invoices),
                ],
            ),
            (
                "💰 SATIŞ",
                [
                    ("📝 Teklifler", self.open_sales_quotes),
                    ("🧾 Siparişler", self.open_sales_orders),
                    ("🚚 İrsaliyeler", self.open_sales_delivery_notes),
                    ("🧾 Faturalar", self.open_sales_invoices),
                ],
            ),
            (
                "🏦 FİNANS",
                [
                    ("💵 Kasa", self.open_cash),
                    ("🏦 Banka", self.open_bank),
                    ("🧾 Çek/Senet", self.open_checks),
                ],
            ),
            ("📈 RAPORLAR", [("📊 Raporlar", self.open_reports)]),
            ("⚙ AYARLAR", [("⚙ Ayarlar", self.open_settings)]),
        ]

        for group_title, items in menu_items:
            group_button = QToolButton()
            group_button.setText(group_title)
            group_button.setCheckable(True)
            group_button.setChecked(True)
            group_button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            group_button.setAutoRaise(True)
            group_button.setStyleSheet(
                "QToolButton{color:white; font-weight:bold; padding:6px; text-align:left;}"
                "QToolButton:checked{background-color:#1e293b;}"
            )
            sidebar_layout.addWidget(group_button)
            self.group_buttons[group_title] = group_button

            group_container = QWidget()
            group_layout = QVBoxLayout(group_container)
            group_layout.setContentsMargins(8, 0, 8, 8)
            group_layout.setSpacing(4)

            for label, callback in items:
                btn = MenuButton(label)
                btn.clicked.connect(callback)
                group_layout.addWidget(btn)

            sidebar_layout.addWidget(group_container)
            self.menu_groups.append((group_button, group_container))

            group_button.toggled.connect(group_container.setVisible)

        sidebar_layout.addStretch()

        sidebar_scroll.setWidget(sidebar_content)
        sidebar_container_layout = QVBoxLayout(self.sidebar)
        sidebar_container_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_container_layout.setSpacing(0)
        sidebar_container_layout.addWidget(sidebar_scroll)

        self.tabs = TabManager()
        self.dashboard = DashboardPage()
        self.tabs.open_tab(self.dashboard, "🏠 Dashboard")

        main_layout.addWidget(self.sidebar, 1)
        main_layout.addWidget(self.tabs, 4)

    def open_dashboard(self):
        self.tabs.open_tab(self.dashboard, "🏠 Dashboard")

    def open_cari_list(self):
        page = CariListPage()
        self.tabs.open_tab(page, "📋 Cari Kartları")

    def open_cari_hareketleri(self):
        self.tabs.open_tab(PlaceholderPage("Cari Hareketleri"), "📄 Cari Hareketleri")

    def open_stock_list(self):
        page = StockListPage()
        self.tabs.open_tab(page, "📦 Stok Kartları")

    def open_stock_categories(self):
        self.tabs.open_tab(PlaceholderPage("Kategoriler"), "🗂 Kategoriler")

    def open_supplier_list(self):
        page = SupplierListPage()
        self.tabs.open_tab(page, "📋 Tedarikçi Kartları")

    def open_purchase_orders(self):
        self.tabs.open_tab(PlaceholderPage("Satın Alma Siparişleri"), "🧾 Siparişler")

    def open_purchase_delivery_notes(self):
        self.tabs.open_tab(PlaceholderPage("Satın Alma İrsaliyeleri"), "🚚 İrsaliyeler")

    def open_purchase_invoices(self):
        self.tabs.open_tab(PlaceholderPage("Satın Alma Faturaları"), "🧾 Faturalar")

    def open_sales_quotes(self):
        self.tabs.open_tab(PlaceholderPage("Teklifler"), "📝 Teklifler")

    def open_sales_orders(self):
        self.tabs.open_tab(PlaceholderPage("Satış Siparişleri"), "🧾 Siparişler")

    def open_sales_delivery_notes(self):
        self.tabs.open_tab(PlaceholderPage("Satış İrsaliyeleri"), "🚚 İrsaliyeler")

    def open_sales_invoices(self):
        self.tabs.open_tab(PlaceholderPage("Satış Faturaları"), "🧾 Faturalar")

    def open_cash(self):
        self.tabs.open_tab(PlaceholderPage("Kasa"), "💵 Kasa")

    def open_bank(self):
        self.tabs.open_tab(PlaceholderPage("Banka"), "🏦 Banka")

    def open_checks(self):
        self.tabs.open_tab(PlaceholderPage("Çek/Senet"), "🧾 Çek/Senet")

    def open_reports(self):
        self.tabs.open_tab(PlaceholderPage("Raporlar"), "📊 Raporlar")

    def open_settings(self):
        self.tabs.open_tab(PlaceholderPage("Ayarlar"), "⚙ Ayarlar")