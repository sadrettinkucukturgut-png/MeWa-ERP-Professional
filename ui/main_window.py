from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
)

from core.tab_manager import TabManager
from ui.dashboard_page import DashboardPage
from shared.widgets.menu_button import MenuButton


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("MeWa ERP Professional")
        self.resize(1400, 800)

        # Ana Widget
        central = QWidget()
        self.setCentralWidget(central)

        # Ana Yerleşim
        ana_layout = QHBoxLayout(central)

        # =========================
        # SOL MENÜ
        # =========================

        menu = QVBoxLayout()

        buttons = [
            "🏠 Dashboard",
            "👥 Cari Yönetimi",
            "📦 Ürünler",
            "💰 Finans",
            "🌍 İhracat",
            "📊 Raporlar",
            "⚙️ Ayarlar",
        ]

        for text in buttons:
            btn = MenuButton(text)
            menu.addWidget(btn)

        menu.addStretch()

        # =========================
        # TAB SİSTEMİ
        # =========================

        self.tabs = TabManager()

        dashboard = DashboardPage()
        self.tabs.open_tab(dashboard, "🏠 Dashboard")

        # =========================

        ana_layout.addLayout(menu, 1)
        ana_layout.addWidget(self.tabs, 4)
        from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
)

from core.tab_manager import TabManager
from shared.widgets.menu_button import MenuButton

from ui.dashboard_page import DashboardPage
from ui.cari_page import CariPage


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("MeWa ERP Professional")
        self.resize(1400, 800)

        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QHBoxLayout(central)

        # ==========================
        # SOL MENÜ
        # ==========================

        menu_layout = QVBoxLayout()

        self.btn_dashboard = MenuButton("🏠 Dashboard")
        self.btn_cari = MenuButton("👥 Cari Yönetimi")
        self.btn_urun = MenuButton("📦 Ürünler")
        self.btn_finans = MenuButton("💰 Finans")
        self.btn_ihracat = MenuButton("🌍 İhracat")
        self.btn_rapor = MenuButton("📊 Raporlar")
        self.btn_ayar = MenuButton("⚙ Ayarlar")

        menu_buttons = [
            self.btn_dashboard,
            self.btn_cari,
            self.btn_urun,
            self.btn_finans,
            self.btn_ihracat,
            self.btn_rapor,
            self.btn_ayar,
        ]

        for btn in menu_buttons:
            menu_layout.addWidget(btn)

        menu_layout.addStretch()

        # ==========================
        # TAB SİSTEMİ
        # ==========================

        self.tabs = TabManager()

        self.dashboard = DashboardPage()
        self.tabs.open_tab(self.dashboard, "🏠 Dashboard")

        # ==========================
        # BUTON OLAYLARI
        # ==========================

        self.btn_dashboard.clicked.connect(self.open_dashboard)
        self.btn_cari.clicked.connect(self.open_cari)

        # ==========================

        main_layout.addLayout(menu_layout, 1)
        main_layout.addWidget(self.tabs, 4)

    # -------------------------

    def open_dashboard(self):
        self.tabs.open_tab(self.dashboard, "🏠 Dashboard")

    def open_cari(self):
        page = CariPage()
        self.tabs.open_tab(page, "👥 Cari Yönetimi")