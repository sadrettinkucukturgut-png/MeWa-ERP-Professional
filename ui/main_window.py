import json

from PySide6.QtCore import QSettings, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QSplitter,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.tab_manager import TabManager
from shared.app_assets import get_company_logo_icon
from ui.cari_hareketleri_dialog import CariHareketleriDialog
from ui.cari_list_page import CariListPage
from ui.dashboard_page import DashboardPage
from ui.cash_page import CashPage
from ui.banks_page import BanksPage
from ui.cash_definitions_page import CashDefinitionsPage
from ui.bank_definitions_page import BankDefinitionsPage
from ui.bank_transactions_page import BankTransactionsPage
from ui.customer_collections_page import CustomerCollectionsPage
from ui.supplier_payments_page import SupplierPaymentsPage
from ui.customer_statement_page import CustomerStatementPage
from ui.cash_flow_page import CashFlowPage
from ui.company_profile_page import CompanyProfilePage
from ui.currency_position_page import CurrencyPositionPage
from ui.finance_reports_page import FinanceReportsPage
from ui.goods_receipt_page import GoodsReceiptPage
from ui.export_sales_invoice_page import ExportSalesInvoicePage
from ui.packing_list_page import PackingListPage
from ui.purchase_invoice_page import PurchaseInvoicePage
from ui.purchase_order_page import PurchaseOrderPage
from ui.proforma_page import ProformaPage
from ui.preferences_page import PreferencesPage
from ui.sidebar_settings_page import SidebarSettingsPage
from ui.stock_list_page import StockListPage
from ui.stock_movement_ledger_page import StockMovementRecordsPage


ROLE_KIND = Qt.UserRole + 1
ROLE_MODULE_ID = Qt.UserRole + 2
ROLE_SUBMENU_ID = Qt.UserRole + 3
ROLE_TEXT_FULL = Qt.UserRole + 4
ROLE_TEXT_ICON = Qt.UserRole + 5
ROLE_FAVORITE_KEY = Qt.UserRole + 6
ROLE_FAVORITE_TYPE = Qt.UserRole + 7
ROLE_FAVORITE_TARGET_ID = Qt.UserRole + 8

KIND_MODULE = "module"
KIND_SUBMENU = "submenu"
KIND_FAVORITE = "favorite"

FAVORITES_MODULE_ID = "__favorites__"


class SidebarTreeWidget(QTreeWidget):
    orderChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._drag_item = None
        self.setHeaderHidden(True)
        self.setAnimated(True)
        self.setIndentation(18)
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setDropIndicatorShown(True)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.setUniformRowHeights(True)
        self.setExpandsOnDoubleClick(False)
        self.verticalScrollBar().setSingleStep(18)
        self.verticalScrollBar().setPageStep(64)
        self.setStyleSheet(
            "QTreeWidget{"
            "background-color:#0f172a;"
            "border:none;"
            "color:white;"
            "outline:none;"
            "padding:0 4px 0 4px;"
            "}"
            "QTreeWidget::item{"
            "height:34px;"
            "border-radius:6px;"
            "padding-left:8px;"
            "}"
            "QTreeWidget::item:hover{"
            "background-color:#1f2a40;"
            "}"
            "QTreeWidget::item:selected{"
            "background-color:#223a56;"
            "}"
            "QTreeView::branch:selected{"
            "background:transparent;"
            "}"
            "QScrollBar:vertical{background:#0f172a; width:8px;}"
            "QScrollBar::handle:vertical{background:#475569; border-radius:4px;}"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical{height:0px;}"
        )

    def set_reorder_enabled(self, enabled: bool) -> None:
        if enabled:
            self.setDragEnabled(True)
            self.viewport().setAcceptDrops(True)
            self.setAcceptDrops(True)
            self.setDragDropMode(QAbstractItemView.InternalMove)
        else:
            self.setDragEnabled(False)
            self.viewport().setAcceptDrops(False)
            self.setAcceptDrops(False)
            self.setDragDropMode(QAbstractItemView.NoDragDrop)

    def startDrag(self, supported_actions):  # noqa: N802
        current = self.currentItem()
        if current is None:
            return
        self._drag_item = current
        super().startDrag(supported_actions)
        self._drag_item = None

    def _item_module_id(self, item: QTreeWidgetItem | None) -> str | None:
        if item is None:
            return None
        if item.parent() is None:
            return str(item.data(0, ROLE_MODULE_ID))
        return str(item.parent().data(0, ROLE_MODULE_ID))

    def dropEvent(self, event):  # noqa: N802
        source_item = self._drag_item or self.currentItem()
        if source_item is None:
            event.ignore()
            return

        # ERP navigation must be reorder-only. Never allow drop-on-item nesting.
        indicator = self.dropIndicatorPosition()
        if indicator == QAbstractItemView.OnItem:
            event.ignore()
            return

        kind = source_item.data(0, ROLE_KIND)
        module_id = self._item_module_id(source_item)
        target_item = self.itemAt(event.position().toPoint())
        target_module_id = self._item_module_id(target_item)

        if kind == KIND_MODULE:
            source_module_id = str(source_item.data(0, ROLE_MODULE_ID))
            if source_module_id == FAVORITES_MODULE_ID:
                event.ignore()
                return
            if indicator == QAbstractItemView.OnItem and target_item is not None:
                event.ignore()
                return
            if source_item.parent() is not None:
                event.ignore()
                return
        elif kind in (KIND_SUBMENU, KIND_FAVORITE):
            if source_item.parent() is None:
                event.ignore()
                return
            if module_id == FAVORITES_MODULE_ID:
                if target_module_id != FAVORITES_MODULE_ID:
                    event.ignore()
                    return
            else:
                if target_module_id != module_id:
                    event.ignore()
                    return
        else:
            event.ignore()
            return

        super().dropEvent(event)
        self.orderChanged.emit()


class PlaceholderPage(QWidget):
    def __init__(self, title: str):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        label = QLabel(f"{title}\n\nYakinda eklenecek")
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("font-size: 20px; color: #64748b;")
        layout.addWidget(label)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.sidebar_expanded_width = 260
        self.sidebar_collapsed_width = 72
        self.sidebar_min_width = 220
        self.sidebar_max_width = 460
        self.sidebar_is_expanded = True
        self.sidebar_locked = False
        self.ui_settings = QSettings("MeWa", "ERP")

        self._module_catalog = {}
        self._submenu_catalog = {}
        self._module_order = []
        self._submenu_orders = {}
        self._hidden_module_ids = set()
        self._favorite_entries = []
        self._expanded_module_ids = set()
        self._suppress_sidebar_state_save = False
        self._sidebar_settings_page = None
        self._preferences_page = None
        self._company_profile_page = None

        self._header_height = 34
        self._group_height = 36

        self.setWindowTitle("MeWa ERP Professional")
        self.resize(1400, 800)
        self.setWindowIcon(get_company_logo_icon())

        central = QWidget()
        self.setCentralWidget(central)

        root_layout = QHBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self.left_panel = QWidget()
        self.left_panel.setStyleSheet("background-color:#0f172a;")
        left_panel_layout = QVBoxLayout(self.left_panel)
        left_panel_layout.setContentsMargins(8, 8, 8, 8)
        left_panel_layout.setSpacing(6)

        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(0, 0, 0, 0)
        top_bar.setSpacing(6)

        self.hamburger_button = QToolButton()
        self.hamburger_button.setText("☰")
        self.hamburger_button.setFixedHeight(self._header_height)
        self.hamburger_button.setCursor(Qt.PointingHandCursor)
        self.hamburger_button.setToolTip("Menuyu Daralt / Genislet")
        self.hamburger_button.setStyleSheet(
            "QToolButton{"
            "color:white;"
            "font-size:18px;"
            "font-weight:bold;"
            "border:none;"
            "padding:0 10px;"
            "text-align:center;"
            "border-radius:6px;"
            "background-color:#172a3f;"
            "}"
            "QToolButton:hover{background-color:#1e293b;}"
        )
        self.hamburger_button.clicked.connect(self._toggle_sidebar)
        top_bar.addWidget(self.hamburger_button)

        self.lock_button = QToolButton()
        self.lock_button.setCheckable(True)
        self.lock_button.setFixedHeight(self._header_height)
        self.lock_button.setCursor(Qt.PointingHandCursor)
        self.lock_button.clicked.connect(self._on_lock_button_clicked)
        self.lock_button.setStyleSheet(
            "QToolButton{"
            "color:white;"
            "font-size:12px;"
            "font-weight:600;"
            "border:none;"
            "padding:0 10px;"
            "text-align:center;"
            "border-radius:6px;"
            "background-color:#172a3f;"
            "}"
            "QToolButton:hover{background-color:#1e293b;}"
        )
        top_bar.addWidget(self.lock_button, 1)

        left_panel_layout.addLayout(top_bar)

        self.sidebar_title = QLabel("MeWa ERP")
        self.sidebar_title.setFixedHeight(self._header_height)
        self.sidebar_title.setStyleSheet(
            "font-size:16px;"
            "font-weight:700;"
            "color:white;"
            "padding-left:10px;"
        )
        left_panel_layout.addWidget(self.sidebar_title)

        self.sidebar_tree = SidebarTreeWidget()
        self.sidebar_tree.itemClicked.connect(self._on_sidebar_item_clicked)
        self.sidebar_tree.itemExpanded.connect(self._on_sidebar_item_expanded)
        self.sidebar_tree.itemCollapsed.connect(self._on_sidebar_item_collapsed)
        self.sidebar_tree.customContextMenuRequested.connect(self._show_sidebar_context_menu)
        self.sidebar_tree.orderChanged.connect(self._on_sidebar_order_changed)
        left_panel_layout.addWidget(self.sidebar_tree, 1)

        self.tabs = TabManager()
        self.dashboard = DashboardPage()
        self.tabs.open_tab(self.dashboard, "🏠 Panel")

        content_container = QWidget()
        content_layout = QVBoxLayout(content_container)
        content_layout.setContentsMargins(0, 0, 10, 8)
        content_layout.setSpacing(0)
        content_layout.addWidget(self.tabs, 1)

        self.main_splitter = QSplitter(Qt.Horizontal)
        self.main_splitter.setChildrenCollapsible(False)
        self.main_splitter.addWidget(self.left_panel)
        self.main_splitter.addWidget(content_container)
        self.main_splitter.setStretchFactor(1, 1)
        self.main_splitter.splitterMoved.connect(self._on_splitter_moved)
        root_layout.addWidget(self.main_splitter)

        self._load_sidebar_catalog()
        self._restore_sidebar_layout_state()
        self._rebuild_sidebar_tree()
        self._apply_sidebar_width_state()
        self._set_sidebar_locked(self.sidebar_locked, save=False)
        self._update_sidebar_text_mode()

    def _load_sidebar_catalog(self) -> None:
        module_defs = [
            {
                "id": "dashboard",
                "icon": "📊",
                "title": "Dashboard",
                "items": [
                    {"id": "panel", "label": "🏠 Panel", "callback": self.open_dashboard},
                ],
            },
            {
                "id": "cari",
                "icon": "👥",
                "title": "Cari",
                "items": [
                    {"id": "cards", "label": "📋 Cari Kartlari", "callback": self.open_cari_list},
                    {"id": "ledger", "label": "📄 Cari Hareket Kayitlari", "callback": self.open_cari_hareketleri},
                    {"id": "reports", "label": "📊 Cari Raporlari", "callback": self.open_cari_reports},
                ],
            },
            {
                "id": "stok",
                "icon": "📦",
                "title": "Stok",
                "items": [
                    {"id": "cards", "label": "📦 Stok Kartlari", "callback": self.open_stock_list},
                    {"id": "movement_ledger", "label": "📒 Stok Hareket Kayıtları", "callback": self.open_stock_movement_ledger},
                    {"id": "reports", "label": "📊 Stok Raporlari", "callback": self.open_stock_reports},
                ],
            },
            {
                "id": "satin_alma",
                "icon": "🛒",
                "title": "Satin Alma",
                "items": [
                    {"id": "purchase_orders", "label": "🧾 Satin Alma Siparisleri", "callback": self.open_purchase_orders},
                    {"id": "goods_receipts", "label": "📦 Mal Kabul", "callback": self.open_goods_receipts},
                    {"id": "purchase_invoices", "label": "🧾 Alis Faturalari", "callback": self.open_purchase_invoices},
                    {"id": "reports", "label": "📊 Satin Alma Raporlari", "callback": self.open_purchase_reports},
                ],
            },
            {
                "id": "satis",
                "icon": "💰",
                "title": "İHRACAT",
                "items": [
                    {"id": "export_invoice", "label": "🧾 Yurtdışı Satış Faturası", "callback": self.open_export_sales_invoice},
                    {"id": "export_quote_proforma", "label": "📄 Teklifler / Proforma", "callback": self.open_export_quote_proforma},
                    {"id": "export_packing_list", "label": "📦 Çeki Listesi / Packing List", "callback": self.open_export_packing_list},
                    {"id": "export_reports", "label": "📊 İhracat Satış Raporları", "callback": self.open_export_sales_reports},
                ],
            },
            {
                "id": "finans",
                "icon": "🏦",
                "title": "Finans",
                "items": [
                    {"id": "cash", "label": "💵 Kasa", "callback": self.open_cash},
                    {"id": "banks", "label": "🏦 Banka Kayıtları", "callback": self.open_banks},
                    {"id": "cash_definitions", "label": "💼 Kasa Tanımları", "callback": self.open_cash_definitions},
                    {"id": "bank_definitions", "label": "🏛 Banka Tanımları", "callback": self.open_bank_definitions},
                    {"id": "reports", "label": "📈 Finans Raporları", "callback": self.open_finance_reports},
                ],
            },
            {
                "id": "raporlar",
                "icon": "📈",
                "title": "Raporlar",
                "items": [
                    {"id": "general", "label": "📊 Genel Raporlar", "callback": self.open_reports},
                    {"id": "analytics", "label": "📉 Dashboard Analizleri", "callback": self.open_dashboard_analytics},
                ],
            },
            {
                "id": "ayarlar",
                "icon": "⚙",
                "title": "Ayarlar",
                "items": [
                    {"id": "company_profile", "label": "🏢 Company Profile", "callback": self.open_company_settings},
                    {"id": "users", "label": "👤 Kullanicilar", "callback": self.open_users},
                    {"id": "authorization", "label": "🛡 Yetkilendirme", "callback": self.open_authorization},
                    {"id": "currency", "label": "💱 Doviz Kurlari", "callback": self.open_currency_rates},
                    {"id": "backup", "label": "🗄 Yedekleme", "callback": self.open_backup},
                    {"id": "sidebar", "label": "🧭 Sidebar Ayarlari", "callback": self.open_sidebar_settings},
                ],
            },
        ]

        self._module_catalog = {module["id"]: module for module in module_defs}
        self._submenu_catalog = {}
        for module in module_defs:
            for submenu in module["items"]:
                submenu_id = self._submenu_key(module["id"], submenu["id"])
                self._submenu_catalog[submenu_id] = {
                    "module_id": module["id"],
                    "label": submenu["label"],
                    "callback": submenu["callback"],
                }

    def _default_module_order(self) -> list[str]:
        return [FAVORITES_MODULE_ID] + list(self._module_catalog.keys())

    def _default_submenu_order_for_module(self, module_id: str) -> list[str]:
        module = self._module_catalog.get(module_id)
        if module is None:
            return []
        return [self._submenu_key(module_id, item["id"]) for item in module["items"]]

    def _normalize_submenu_order(self, module_id: str, saved_order: list[str]) -> list[str]:
        allowed = self._default_submenu_order_for_module(module_id)
        result = []
        for submenu_id in saved_order:
            if submenu_id in allowed and submenu_id not in result:
                result.append(submenu_id)
        for submenu_id in allowed:
            if submenu_id not in result:
                result.append(submenu_id)
        return result

    def _favorite_key_for_submenu(self, submenu_id: str) -> str:
        return f"submenu:{submenu_id}"

    def _favorite_key_for_module(self, module_id: str) -> str:
        return f"module:{module_id}"

    def _parse_favorite_key(self, key: str) -> tuple[str, str] | None:
        if not isinstance(key, str):
            return None
        if key.startswith("submenu:"):
            submenu_id = key[len("submenu:") :]
            if submenu_id in self._submenu_catalog:
                return ("submenu", submenu_id)
            return None
        if key.startswith("module:"):
            module_id = key[len("module:") :]
            if module_id in self._module_catalog:
                return ("module", module_id)
            return None
        return None

    def _normalize_favorites(self, saved_entries: list[str]) -> list[str]:
        normalized = []
        for entry in saved_entries:
            parsed = self._parse_favorite_key(entry)
            if parsed is None:
                continue
            if entry not in normalized:
                normalized.append(entry)
        return normalized

    def _submenu_key(self, module_id: str, item_id: str) -> str:
        return f"{module_id}:{item_id}"

    def _read_list_setting(self, key: str) -> list[str]:
        value = self.ui_settings.value(key, [])
        if isinstance(value, str):
            if not value.strip():
                return []
            return [part for part in value.split("|") if part]
        if isinstance(value, list):
            return [str(part) for part in value if str(part).strip()]
        return []

    def _normalize_order(self, saved_order: list[str]) -> list[str]:
        allowed = self._default_module_order()
        result = []
        for module_id in saved_order:
            if module_id in allowed and module_id not in result:
                result.append(module_id)
        for module_id in allowed:
            if module_id not in result:
                result.append(module_id)
        return result

    def _restore_sidebar_layout_state(self) -> None:
        saved_order = self._read_list_setting("sidebar/layout/order")
        self._module_order = self._normalize_order(saved_order)

        submenu_orders_raw = self.ui_settings.value("sidebar/layout/submenu_orders_json", "{}")
        if isinstance(submenu_orders_raw, str):
            try:
                parsed_submenu_orders = json.loads(submenu_orders_raw)
            except Exception:
                parsed_submenu_orders = {}
        elif isinstance(submenu_orders_raw, dict):
            parsed_submenu_orders = submenu_orders_raw
        else:
            parsed_submenu_orders = {}

        self._submenu_orders = {}
        for module_id in self._module_catalog.keys():
            saved_sub_order = parsed_submenu_orders.get(module_id, [])
            if not isinstance(saved_sub_order, list):
                saved_sub_order = []
            saved_sub_order = [str(entry) for entry in saved_sub_order]
            self._submenu_orders[module_id] = self._normalize_submenu_order(module_id, saved_sub_order)

        hidden = self._read_list_setting("sidebar/layout/hidden_modules")
        self._hidden_module_ids = {module_id for module_id in hidden if module_id in self._module_catalog}

        favorites_v2 = self._read_list_setting("sidebar/layout/favorites_v2")
        if favorites_v2:
            self._favorite_entries = self._normalize_favorites(favorites_v2)
        else:
            favorites_legacy = self._read_list_setting("sidebar/layout/favorites")
            migrated = [
                self._favorite_key_for_submenu(submenu_id)
                for submenu_id in favorites_legacy
                if submenu_id in self._submenu_catalog
            ]
            self._favorite_entries = self._normalize_favorites(migrated)

        expanded = self._read_list_setting("sidebar/layout/expanded_modules")
        self._expanded_module_ids = {
            module_id
            for module_id in expanded
            if module_id in self._module_catalog or module_id == FAVORITES_MODULE_ID
        }
        if not self._expanded_module_ids:
            self._expanded_module_ids = {"dashboard"}

        locked_value = str(self.ui_settings.value("sidebar/layout/locked", "false")).lower()
        self.sidebar_locked = locked_value == "true"

        is_expanded_value = self.ui_settings.value(
            "sidebar/layout/is_expanded",
            self.ui_settings.value("sidebar/is_expanded", "true"),
        )
        self.sidebar_is_expanded = str(is_expanded_value).lower() == "true"

        width_value = self.ui_settings.value("sidebar/layout/width", self.sidebar_expanded_width)
        try:
            parsed_width = int(width_value)
        except (TypeError, ValueError):
            parsed_width = self.sidebar_expanded_width
        self.sidebar_expanded_width = max(self.sidebar_min_width, min(parsed_width, self.sidebar_max_width))

    def _save_sidebar_layout_state(self) -> None:
        if self._suppress_sidebar_state_save:
            return
        self.ui_settings.setValue("sidebar/layout/order", self._module_order)
        self.ui_settings.setValue("sidebar/layout/submenu_orders_json", json.dumps(self._submenu_orders, ensure_ascii=True))
        self.ui_settings.setValue("sidebar/layout/hidden_modules", sorted(self._hidden_module_ids))
        self.ui_settings.setValue("sidebar/layout/favorites_v2", self._favorite_entries)
        self.ui_settings.setValue("sidebar/layout/expanded_modules", sorted(self._expanded_module_ids))
        self.ui_settings.setValue("sidebar/layout/locked", self.sidebar_locked)
        self.ui_settings.setValue("sidebar/layout/is_expanded", self.sidebar_is_expanded)
        self.ui_settings.setValue("sidebar/layout/width", self.sidebar_expanded_width)
        self.ui_settings.setValue("sidebar/is_expanded", self.sidebar_is_expanded)

    def _rebuild_sidebar_tree(self) -> None:
        self._suppress_sidebar_state_save = True
        self.sidebar_tree.clear()

        visible_module_ids = [
            module_id
            for module_id in self._module_order
            if module_id == FAVORITES_MODULE_ID or module_id not in self._hidden_module_ids
        ]

        for module_id in visible_module_ids:
            if module_id == FAVORITES_MODULE_ID:
                if not self._favorite_entries:
                    continue
                module_item = self._create_module_item(FAVORITES_MODULE_ID, "⭐ Favorites")
                for favorite_key in self._favorite_entries:
                    parsed = self._parse_favorite_key(favorite_key)
                    if parsed is None:
                        continue
                    favorite_type, target_id = parsed
                    if favorite_type == "submenu":
                        submenu = self._submenu_catalog.get(target_id)
                        if submenu is None:
                            continue
                        favorite_label = submenu["label"]
                    else:
                        module = self._module_catalog.get(target_id)
                        if module is None:
                            continue
                        favorite_label = f"{module['icon']} {module['title']}"
                    child = self._create_favorite_item(favorite_key, favorite_type, target_id, f"⭐ {favorite_label}")
                    module_item.addChild(child)
                self.sidebar_tree.addTopLevelItem(module_item)
                module_item.setExpanded(FAVORITES_MODULE_ID in self._expanded_module_ids)
                continue

            module = self._module_catalog.get(module_id)
            if module is None:
                continue

            module_label = f"{module['icon']}  {module['title']}"
            module_item = self._create_module_item(module_id, module_label)
            for submenu_id in self._submenu_orders.get(module_id, self._default_submenu_order_for_module(module_id)):
                submenu = self._submenu_catalog.get(submenu_id)
                if submenu is None:
                    continue
                child = self._create_submenu_item(submenu_id, submenu["label"])
                module_item.addChild(child)
            self.sidebar_tree.addTopLevelItem(module_item)
            module_item.setExpanded(module_id in self._expanded_module_ids)

        self._set_sidebar_locked(self.sidebar_locked, save=False)
        self._update_sidebar_text_mode()
        self._suppress_sidebar_state_save = False

    def _create_module_item(self, module_id: str, full_text: str) -> QTreeWidgetItem:
        item = QTreeWidgetItem([full_text])
        icon_only = full_text.split(" ", 1)[0]
        item.setData(0, ROLE_KIND, KIND_MODULE)
        item.setData(0, ROLE_MODULE_ID, module_id)
        item.setData(0, ROLE_TEXT_FULL, full_text)
        item.setData(0, ROLE_TEXT_ICON, icon_only)
        item.setFlags(
            Qt.ItemIsEnabled
            | Qt.ItemIsSelectable
            | Qt.ItemIsDropEnabled
            | Qt.ItemIsDragEnabled
        )
        if module_id == FAVORITES_MODULE_ID:
            item.setFlags((item.flags() | Qt.ItemIsDropEnabled) & ~Qt.ItemIsDragEnabled)
        return item

    def _create_submenu_item(self, submenu_id: str, full_text: str) -> QTreeWidgetItem:
        item = QTreeWidgetItem([full_text])
        icon_only = full_text.split(" ", 1)[0]
        item.setData(0, ROLE_KIND, KIND_SUBMENU)
        item.setData(0, ROLE_SUBMENU_ID, submenu_id)
        item.setData(0, ROLE_TEXT_FULL, full_text)
        item.setData(0, ROLE_TEXT_ICON, icon_only)
        item.setFlags(
            Qt.ItemIsEnabled
            | Qt.ItemIsSelectable
            | Qt.ItemIsDragEnabled
        )
        return item

    def _create_favorite_item(
        self,
        favorite_key: str,
        favorite_type: str,
        target_id: str,
        full_text: str,
    ) -> QTreeWidgetItem:
        item = QTreeWidgetItem([full_text])
        icon_only = full_text.split(" ", 2)[1] if " " in full_text else full_text
        item.setData(0, ROLE_KIND, KIND_FAVORITE)
        item.setData(0, ROLE_FAVORITE_KEY, favorite_key)
        item.setData(0, ROLE_FAVORITE_TYPE, favorite_type)
        item.setData(0, ROLE_FAVORITE_TARGET_ID, target_id)
        item.setData(0, ROLE_TEXT_FULL, full_text)
        item.setData(0, ROLE_TEXT_ICON, icon_only)
        item.setFlags(
            Qt.ItemIsEnabled
            | Qt.ItemIsSelectable
            | Qt.ItemIsDragEnabled
        )
        return item

    def _apply_sidebar_width_state(self) -> None:
        if self.sidebar_is_expanded:
            self.left_panel.setMinimumWidth(self.sidebar_min_width)
            self.left_panel.setMaximumWidth(self.sidebar_max_width)
            self.main_splitter.setSizes([self.sidebar_expanded_width, max(900, self.width() - self.sidebar_expanded_width)])
        else:
            self.left_panel.setMinimumWidth(self.sidebar_collapsed_width)
            self.left_panel.setMaximumWidth(self.sidebar_collapsed_width)
            self.main_splitter.setSizes([self.sidebar_collapsed_width, max(900, self.width() - self.sidebar_collapsed_width)])

    def _toggle_sidebar(self) -> None:
        self.sidebar_is_expanded = not self.sidebar_is_expanded
        self._apply_sidebar_width_state()
        self._set_sidebar_locked(self.sidebar_locked, save=False)
        self._update_sidebar_text_mode()
        self._save_sidebar_layout_state()

    def _set_sidebar_locked(self, locked: bool, save: bool = True) -> None:
        self.sidebar_locked = bool(locked)
        self.lock_button.blockSignals(True)
        self.lock_button.setChecked(self.sidebar_locked)
        self.lock_button.setText("🔒 Lock Sidebar" if self.sidebar_locked else "🔓 Lock Sidebar")
        self.lock_button.setToolTip("Locked: fixed layout" if self.sidebar_locked else "Unlocked: drag, hide, and pin enabled")
        self.lock_button.blockSignals(False)

        can_reorder = (not self.sidebar_locked) and self.sidebar_is_expanded
        self.sidebar_tree.set_reorder_enabled(can_reorder)
        if save:
            self._save_sidebar_layout_state()

    def _on_lock_button_clicked(self) -> None:
        self._set_sidebar_locked(self.lock_button.isChecked(), save=True)

    def _on_sidebar_item_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        _ = column
        kind = item.data(0, ROLE_KIND)
        if kind == KIND_MODULE:
            item.setExpanded(not item.isExpanded())
            return

        if kind == KIND_FAVORITE:
            favorite_type = str(item.data(0, ROLE_FAVORITE_TYPE))
            target_id = str(item.data(0, ROLE_FAVORITE_TARGET_ID))
            if favorite_type == "submenu":
                submenu = self._submenu_catalog.get(target_id)
                if submenu is None:
                    return
                submenu["callback"]()
                return
            module = self._module_catalog.get(target_id)
            if module is None or not module["items"]:
                return
            first_item = module["items"][0]
            submenu_id = self._submenu_key(target_id, first_item["id"])
            submenu = self._submenu_catalog.get(submenu_id)
            if submenu is None:
                return
            submenu["callback"]()
            return

        submenu_id = item.data(0, ROLE_SUBMENU_ID)
        submenu = self._submenu_catalog.get(str(submenu_id))
        if submenu is None:
            return

        callback = submenu["callback"]
        callback()

    def _on_sidebar_item_expanded(self, item: QTreeWidgetItem) -> None:
        if item.data(0, ROLE_KIND) != KIND_MODULE:
            return
        module_id = str(item.data(0, ROLE_MODULE_ID))
        self._expanded_module_ids.add(module_id)
        self._save_sidebar_layout_state()

    def _on_sidebar_item_collapsed(self, item: QTreeWidgetItem) -> None:
        if item.data(0, ROLE_KIND) != KIND_MODULE:
            return
        module_id = str(item.data(0, ROLE_MODULE_ID))
        if module_id in self._expanded_module_ids:
            self._expanded_module_ids.remove(module_id)
            self._save_sidebar_layout_state()

    def _on_sidebar_order_changed(self) -> None:
        if self.sidebar_locked:
            return

        visible_order = []
        for index in range(self.sidebar_tree.topLevelItemCount()):
            module_item = self.sidebar_tree.topLevelItem(index)
            module_id = str(module_item.data(0, ROLE_MODULE_ID))
            if module_id not in visible_order:
                visible_order.append(module_id)

            if module_id == FAVORITES_MODULE_ID:
                favorites = []
                for child_index in range(module_item.childCount()):
                    child = module_item.child(child_index)
                    favorite_key = str(child.data(0, ROLE_FAVORITE_KEY) or "")
                    if favorite_key and favorite_key not in favorites:
                        favorites.append(favorite_key)
                self._favorite_entries = self._normalize_favorites(favorites)
                continue

            submenu_order = []
            for child_index in range(module_item.childCount()):
                child = module_item.child(child_index)
                submenu_id = str(child.data(0, ROLE_SUBMENU_ID) or "")
                if submenu_id and submenu_id not in submenu_order:
                    submenu_order.append(submenu_id)
            self._submenu_orders[module_id] = self._normalize_submenu_order(module_id, submenu_order)

        merged = []
        for module_id in visible_order:
            if module_id not in merged:
                merged.append(module_id)

        for module_id in self._module_order:
            if module_id not in merged:
                merged.append(module_id)

        self._module_order = self._normalize_order(merged)
        self._save_sidebar_layout_state()

    def _show_sidebar_context_menu(self, pos) -> None:
        item = self.sidebar_tree.itemAt(pos)
        if item is None:
            return

        kind = item.data(0, ROLE_KIND)
        menu = QMenu(self)

        if kind == KIND_MODULE:
            module_id = str(item.data(0, ROLE_MODULE_ID))
            if module_id != FAVORITES_MODULE_ID:
                module_favorite_key = self._favorite_key_for_module(module_id)
                if module_favorite_key in self._favorite_entries:
                    unpin_module = menu.addAction("Remove from Favorites")
                    unpin_module.setEnabled(not self.sidebar_locked)
                    unpin_module.triggered.connect(lambda: self._set_favorite(module_favorite_key, False))
                else:
                    pin_module = menu.addAction("Add to Favorites")
                    pin_module.setEnabled(not self.sidebar_locked)
                    pin_module.triggered.connect(lambda: self._set_favorite(module_favorite_key, True))

            if module_id != FAVORITES_MODULE_ID:
                hide_action = menu.addAction("Hide Module")
                hide_action.setEnabled(not self.sidebar_locked)
                hide_action.triggered.connect(lambda: self._set_module_hidden(module_id, True))

                move_top_action = menu.addAction("Move to Top")
                move_top_action.setEnabled(not self.sidebar_locked)
                move_top_action.triggered.connect(lambda: self._move_module_to_edge(module_id, True))

                move_bottom_action = menu.addAction("Move to Bottom")
                move_bottom_action.setEnabled(not self.sidebar_locked)
                move_bottom_action.triggered.connect(lambda: self._move_module_to_edge(module_id, False))

                restore_default_order_action = menu.addAction("Restore Default Order")
                restore_default_order_action.setEnabled(not self.sidebar_locked)
                restore_default_order_action.triggered.connect(self._restore_default_module_order)

            expand_action = menu.addAction("Expand" if not item.isExpanded() else "Collapse")
            expand_action.triggered.connect(lambda: item.setExpanded(not item.isExpanded()))

            if module_id == FAVORITES_MODULE_ID:
                clear_favorites = menu.addAction("Clear Favorites")
                clear_favorites.setEnabled((not self.sidebar_locked) and bool(self._favorite_entries))
                clear_favorites.triggered.connect(self._clear_favorites)
                restore_favorites_order = menu.addAction("Restore Default Order")
                restore_favorites_order.setEnabled(not self.sidebar_locked)
                restore_favorites_order.triggered.connect(self._restore_default_favorites)

        elif kind == KIND_SUBMENU:
            submenu_id = str(item.data(0, ROLE_SUBMENU_ID))
            favorite_key = self._favorite_key_for_submenu(submenu_id)
            is_favorite = favorite_key in self._favorite_entries
            parent = item.parent()
            parent_module_id = str(parent.data(0, ROLE_MODULE_ID)) if parent is not None else ""

            if is_favorite:
                unpin_action = menu.addAction("Remove from Favorites")
                unpin_action.setEnabled(not self.sidebar_locked)
                unpin_action.triggered.connect(lambda: self._set_favorite(favorite_key, False))
            else:
                pin_action = menu.addAction("Add to Favorites")
                pin_action.setEnabled(not self.sidebar_locked)
                pin_action.triggered.connect(lambda: self._set_favorite(favorite_key, True))

            move_top = menu.addAction("Move to Top")
            move_top.setEnabled(not self.sidebar_locked)
            move_top.triggered.connect(lambda: self._move_submenu_to_edge(parent_module_id, submenu_id, True))

            move_bottom = menu.addAction("Move to Bottom")
            move_bottom.setEnabled(not self.sidebar_locked)
            move_bottom.triggered.connect(lambda: self._move_submenu_to_edge(parent_module_id, submenu_id, False))

            restore_default = menu.addAction("Restore Default Order")
            restore_default.setEnabled(not self.sidebar_locked)
            restore_default.triggered.connect(lambda: self._restore_default_submenu_order(parent_module_id))

        elif kind == KIND_FAVORITE:
            favorite_key = str(item.data(0, ROLE_FAVORITE_KEY))
            favorite_type = str(item.data(0, ROLE_FAVORITE_TYPE))
            target_id = str(item.data(0, ROLE_FAVORITE_TARGET_ID))

            remove_action = menu.addAction("Remove from Favorites")
            remove_action.setEnabled(not self.sidebar_locked)
            remove_action.triggered.connect(lambda: self._set_favorite(favorite_key, False))

            if favorite_type == "module" and target_id in self._module_catalog:
                hide_action = menu.addAction("Hide Module")
                hide_action.setEnabled(not self.sidebar_locked)
                hide_action.triggered.connect(lambda: self._set_module_hidden(target_id, True))

            move_up = menu.addAction("Move Up")
            move_up.setEnabled(not self.sidebar_locked)
            move_up.triggered.connect(lambda: self._move_favorite_by_step(favorite_key, -1))

            move_down = menu.addAction("Move Down")
            move_down.setEnabled(not self.sidebar_locked)
            move_down.triggered.connect(lambda: self._move_favorite_by_step(favorite_key, 1))

            move_top = menu.addAction("Move to Top")
            move_top.setEnabled(not self.sidebar_locked)
            move_top.triggered.connect(lambda: self._move_favorite_to_edge(favorite_key, True))

            move_bottom = menu.addAction("Move to Bottom")
            move_bottom.setEnabled(not self.sidebar_locked)
            move_bottom.triggered.connect(lambda: self._move_favorite_to_edge(favorite_key, False))

            restore_favorites_order = menu.addAction("Restore Default Order")
            restore_favorites_order.setEnabled(not self.sidebar_locked)
            restore_favorites_order.triggered.connect(self._restore_default_favorites)

        if menu.actions():
            menu.exec_(self.sidebar_tree.viewport().mapToGlobal(pos))

    def _set_module_hidden(self, module_id: str, hidden: bool) -> None:
        if module_id not in self._module_catalog:
            return
        if hidden:
            self._hidden_module_ids.add(module_id)
            self._expanded_module_ids.discard(module_id)
        else:
            self._hidden_module_ids.discard(module_id)
        self._rebuild_sidebar_tree()
        self._save_sidebar_layout_state()

    def _hidden_modules_for_settings(self) -> list[tuple[str, str]]:
        hidden = []
        for module_id in self._module_order:
            if module_id == FAVORITES_MODULE_ID:
                continue
            if module_id in self._hidden_module_ids and module_id in self._module_catalog:
                hidden.append((module_id, self._module_catalog[module_id]["title"]))
        return hidden

    def _show_hidden_modules(self) -> None:
        self._hidden_module_ids.clear()
        self._rebuild_sidebar_tree()
        self._save_sidebar_layout_state()

    def _restore_hidden_modules(self) -> None:
        self._show_hidden_modules()

    def _on_sidebar_settings_visibility_changed(self, module_id: str, hidden: bool) -> None:
        self._set_module_hidden(module_id, hidden)

    def _reset_sidebar_layout(self) -> None:
        self._module_order = self._default_module_order()
        self._submenu_orders = {
            module_id: self._default_submenu_order_for_module(module_id)
            for module_id in self._module_catalog.keys()
        }
        self._hidden_module_ids.clear()
        self._favorite_entries = []
        self._expanded_module_ids = {"dashboard"}
        self.sidebar_is_expanded = True
        self.sidebar_locked = False
        self.sidebar_expanded_width = 260

        self._rebuild_sidebar_tree()
        self._apply_sidebar_width_state()
        self._set_sidebar_locked(False, save=False)
        self._update_sidebar_text_mode()
        self._save_sidebar_layout_state()

    def _set_favorite(self, favorite_key: str, enabled: bool) -> None:
        parsed = self._parse_favorite_key(favorite_key)
        if parsed is None:
            return

        if enabled:
            if favorite_key not in self._favorite_entries:
                self._favorite_entries.append(favorite_key)
            if FAVORITES_MODULE_ID not in self._module_order:
                self._module_order.insert(0, FAVORITES_MODULE_ID)
            self._expanded_module_ids.add(FAVORITES_MODULE_ID)
        else:
            self._favorite_entries = [
                item_id for item_id in self._favorite_entries if item_id != favorite_key
            ]
            if not self._favorite_entries:
                self._expanded_module_ids.discard(FAVORITES_MODULE_ID)

        self._rebuild_sidebar_tree()
        self._save_sidebar_layout_state()

    def _clear_favorites(self) -> None:
        self._favorite_entries = []
        self._expanded_module_ids.discard(FAVORITES_MODULE_ID)
        self._rebuild_sidebar_tree()
        self._save_sidebar_layout_state()

    def _move_module_to_edge(self, module_id: str, move_top: bool) -> None:
        if self.sidebar_locked or module_id not in self._module_catalog:
            return
        order_without = [item for item in self._module_order if item != module_id]
        insert_pos = 1 if move_top else len(order_without)
        order_without.insert(insert_pos, module_id)
        self._module_order = self._normalize_order(order_without)
        self._rebuild_sidebar_tree()
        self._save_sidebar_layout_state()

    def _restore_default_module_order(self) -> None:
        if self.sidebar_locked:
            return
        default_without_favorites = [
            module_id
            for module_id in self._default_module_order()
            if module_id != FAVORITES_MODULE_ID
        ]
        self._module_order = [FAVORITES_MODULE_ID] + default_without_favorites
        self._rebuild_sidebar_tree()
        self._save_sidebar_layout_state()

    def _move_submenu_to_edge(self, module_id: str, submenu_id: str, move_top: bool) -> None:
        if self.sidebar_locked:
            return
        if module_id == FAVORITES_MODULE_ID:
            favorite_key = str(submenu_id)
            self._move_favorite_to_edge(favorite_key, move_top)
            return
        if module_id not in self._submenu_orders:
            return
        current = [item for item in self._submenu_orders[module_id] if item != submenu_id]
        if submenu_id not in self._submenu_catalog:
            return
        insert_pos = 0 if move_top else len(current)
        current.insert(insert_pos, submenu_id)
        self._submenu_orders[module_id] = self._normalize_submenu_order(module_id, current)
        self._rebuild_sidebar_tree()
        self._save_sidebar_layout_state()

    def _restore_default_submenu_order(self, module_id: str) -> None:
        if self.sidebar_locked or module_id not in self._module_catalog:
            return
        self._submenu_orders[module_id] = self._default_submenu_order_for_module(module_id)
        self._rebuild_sidebar_tree()
        self._save_sidebar_layout_state()

    def _move_favorite_to_edge(self, favorite_key: str, move_top: bool) -> None:
        if self.sidebar_locked or favorite_key not in self._favorite_entries:
            return
        current = [item for item in self._favorite_entries if item != favorite_key]
        insert_pos = 0 if move_top else len(current)
        current.insert(insert_pos, favorite_key)
        self._favorite_entries = self._normalize_favorites(current)
        self._rebuild_sidebar_tree()
        self._save_sidebar_layout_state()

    def _move_favorite_by_step(self, favorite_key: str, step: int) -> None:
        if self.sidebar_locked or favorite_key not in self._favorite_entries:
            return
        current = list(self._favorite_entries)
        current_index = current.index(favorite_key)
        new_index = max(0, min(len(current) - 1, current_index + step))
        if new_index == current_index:
            return
        current.pop(current_index)
        current.insert(new_index, favorite_key)
        self._favorite_entries = self._normalize_favorites(current)
        self._rebuild_sidebar_tree()
        self._save_sidebar_layout_state()

    def _restore_default_favorites(self) -> None:
        if self.sidebar_locked:
            return
        self._favorite_entries = []
        self._expanded_module_ids.discard(FAVORITES_MODULE_ID)
        self._rebuild_sidebar_tree()
        self._save_sidebar_layout_state()

    def _export_sidebar_layout(self) -> None:
        payload = {
            "module_order": self._module_order,
            "submenu_orders": self._submenu_orders,
            "hidden_modules": sorted(self._hidden_module_ids),
            "favorites": self._favorite_entries,
            "expanded_modules": sorted(self._expanded_module_ids),
            "is_expanded": self.sidebar_is_expanded,
            "width": self.sidebar_expanded_width,
            "locked": self.sidebar_locked,
        }
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Sidebar Layout",
            "sidebar_layout.json",
            "JSON Files (*.json)",
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as file_obj:
                json.dump(payload, file_obj, ensure_ascii=False, indent=2)
        except Exception as exc:
            QMessageBox.warning(self, "Export Sidebar Layout", f"Export failed: {exc}")

    def _import_sidebar_layout(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Import Sidebar Layout",
            "",
            "JSON Files (*.json)",
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as file_obj:
                payload = json.load(file_obj)
        except Exception as exc:
            QMessageBox.warning(self, "Import Sidebar Layout", f"Import failed: {exc}")
            return

        module_order = payload.get("module_order", [])
        submenu_orders = payload.get("submenu_orders", {})
        hidden_modules = payload.get("hidden_modules", [])
        favorites = payload.get("favorites", [])
        expanded_modules = payload.get("expanded_modules", [])

        self._module_order = self._normalize_order([str(entry) for entry in module_order])
        self._submenu_orders = {}
        for module_id in self._module_catalog.keys():
            saved_sub_order = submenu_orders.get(module_id, []) if isinstance(submenu_orders, dict) else []
            if not isinstance(saved_sub_order, list):
                saved_sub_order = []
            self._submenu_orders[module_id] = self._normalize_submenu_order(
                module_id,
                [str(entry) for entry in saved_sub_order],
            )
        self._hidden_module_ids = {
            str(module_id)
            for module_id in hidden_modules
            if str(module_id) in self._module_catalog
        }
        self._favorite_entries = self._normalize_favorites([str(entry) for entry in favorites])
        self._expanded_module_ids = {
            str(module_id)
            for module_id in expanded_modules
            if str(module_id) in self._module_catalog or str(module_id) == FAVORITES_MODULE_ID
        }
        if not self._expanded_module_ids:
            self._expanded_module_ids = {"dashboard"}

        self.sidebar_is_expanded = bool(payload.get("is_expanded", True))
        imported_width = payload.get("width", 260)
        try:
            self.sidebar_expanded_width = max(
                self.sidebar_min_width,
                min(int(imported_width), self.sidebar_max_width),
            )
        except (TypeError, ValueError):
            self.sidebar_expanded_width = 260
        self.sidebar_locked = bool(payload.get("locked", False))

        self._rebuild_sidebar_tree()
        self._apply_sidebar_width_state()
        self._set_sidebar_locked(self.sidebar_locked, save=False)
        self._update_sidebar_text_mode()
        self._save_sidebar_layout_state()

    def _update_sidebar_text_mode(self) -> None:
        self.sidebar_title.setVisible(self.sidebar_is_expanded)

        for index in range(self.sidebar_tree.topLevelItemCount()):
            module_item = self.sidebar_tree.topLevelItem(index)
            self._apply_item_text_mode(module_item)
            for child_index in range(module_item.childCount()):
                self._apply_item_text_mode(module_item.child(child_index))

    def _apply_item_text_mode(self, item: QTreeWidgetItem) -> None:
        full_text = str(item.data(0, ROLE_TEXT_FULL) or "")
        icon_text = str(item.data(0, ROLE_TEXT_ICON) or "")
        item.setToolTip(0, full_text)
        item.setText(0, full_text if self.sidebar_is_expanded else icon_text)

    def _on_splitter_moved(self, _pos: int, _index: int) -> None:
        if not self.sidebar_is_expanded:
            return
        width = self.left_panel.width()
        clamped = max(self.sidebar_min_width, min(width, self.sidebar_max_width))
        if clamped != self.sidebar_expanded_width:
            self.sidebar_expanded_width = clamped
            self._save_sidebar_layout_state()

    def resizeEvent(self, event):  # noqa: N802
        super().resizeEvent(event)

    def open_dashboard(self):
        self.tabs.open_tab(self.dashboard, "🏠 Panel")

    def open_cari_list(self):
        page = CariListPage()
        self.tabs.open_tab(page, "📋 Cari Kartlari")

    def open_cari_hareketleri(self):
        try:
            page = CariHareketleriDialog()
            self.tabs.open_tab(page, "📄 Cari Hareket Kayitlari")
        except Exception as e:
            print(f"Customer Ledger open error: {e}")

    def open_cari_reports(self):
        self.tabs.open_tab(PlaceholderPage("Cari Raporlari"), "📊 Cari Raporlari")

    def open_stock_list(self):
        page = StockListPage()
        self.tabs.open_tab(page, "📦 Stok Kartlari")

    def open_stock_categories(self):
        self.tabs.open_tab(PlaceholderPage("Kategoriler"), "🗂 Kategoriler")

    def open_stock_warehouses(self):
        self.tabs.open_tab(PlaceholderPage("Depolar"), "🏬 Depolar")

    def open_stock_brands(self):
        self.tabs.open_tab(PlaceholderPage("Markalar"), "🏷 Markalar")

    def open_stock_movement_ledger(self):
        page = StockMovementRecordsPage()
        self.tabs.open_tab(page, "📒 Stok Hareket Kayıtları")

    def open_stock_reports(self):
        self.tabs.open_tab(PlaceholderPage("Stok Raporlari"), "📊 Stok Raporlari")

    def open_purchase_orders(self):
        page = PurchaseOrderPage()
        self.tabs.open_tab(page, "🧾 Satin Alma Siparisleri")

    def open_goods_receipts(self):
        page = GoodsReceiptPage()
        self.tabs.open_tab(page, "📦 Mal Kabul")

    def open_purchase_delivery_notes(self):
        self.tabs.open_tab(PlaceholderPage("Satin Alma Irsaliyeleri"), "🚚 Irsaliyeler")

    def open_purchase_invoices(self):
        page = PurchaseInvoicePage()
        self.tabs.open_tab(page, "🧾 Alis Faturalari")

    def open_purchase_reports(self):
        self.tabs.open_tab(PlaceholderPage("Satin Alma Raporlari"), "📊 Satin Alma Raporlari")

    def open_export_sales_invoice(self):
        page = ExportSalesInvoicePage()
        self.tabs.open_tab(page, "🧾 Yurtdışı Satış Faturası")

    def open_export_quote_proforma(self):
        page = ProformaPage()
        self.tabs.open_tab(page, "📄 Teklifler / Proforma")

    def open_export_packing_list(self):
        page = PackingListPage()
        self.tabs.open_tab(page, "📦 Çeki Listesi / Packing List")

    def open_export_sales_reports(self):
        page = ExportSalesInvoicePage()
        self.tabs.open_tab(page, "📊 İhracat Satış Raporları")

    def open_cash(self):
        self.tabs.open_tab(CashPage(), "💵 Kasa")

    def open_banks(self):
        self.tabs.open_tab(BanksPage(), "🏦 Banka Kayıtları")

    def open_cash_definitions(self):
        self.tabs.open_tab(CashDefinitionsPage(), "💼 Kasa Tanımları")

    def open_bank_definitions(self):
        self.tabs.open_tab(BankDefinitionsPage(), "🏛 Banka Tanımları")

    def open_bank_transactions(self):
        self.tabs.open_tab(BankTransactionsPage(), "📒 Bank Transactions")

    def open_customer_collections(self):
        self.tabs.open_tab(CustomerCollectionsPage(), "💳 Customer Collections")

    def open_supplier_payments(self):
        self.tabs.open_tab(SupplierPaymentsPage(), "💸 Supplier Payments")

    def open_customer_statement(self):
        self.tabs.open_tab(CustomerStatementPage(), "📄 Customer Statement")

    def open_cash_flow(self):
        self.tabs.open_tab(CashFlowPage(), "📊 Cash Flow")

    def open_currency_position(self):
        self.tabs.open_tab(CurrencyPositionPage(), "💱 Currency Position")

    def open_finance_reports(self):
        self.tabs.open_tab(FinanceReportsPage(), "📈 Finans Raporları")

    def open_reports(self):
        self.tabs.open_tab(PlaceholderPage("Genel Raporlar"), "📊 Genel Raporlar")

    def open_dashboard_analytics(self):
        self.tabs.open_tab(PlaceholderPage("Dashboard Analizleri"), "📉 Dashboard Analizleri")

    def open_settings(self):
        if self._preferences_page is None:
            self._preferences_page = PreferencesPage()
        self.tabs.open_tab(self._preferences_page, "⚙ Preferences")

    def open_sidebar_settings(self):
        if self._sidebar_settings_page is None:
            self._sidebar_settings_page = SidebarSettingsPage(self._hidden_modules_for_settings())
            self._sidebar_settings_page.showHiddenRequested.connect(self._show_hidden_modules)
            self._sidebar_settings_page.restoreHiddenRequested.connect(self._restore_hidden_modules)
            self._sidebar_settings_page.moduleVisibilityChanged.connect(self._on_sidebar_settings_visibility_changed)
            self._sidebar_settings_page.resetRequested.connect(self._reset_sidebar_layout)
            self._sidebar_settings_page.exportRequested.connect(self._export_sidebar_layout)
            self._sidebar_settings_page.importRequested.connect(self._import_sidebar_layout)
        else:
            self._sidebar_settings_page.set_hidden_modules(self._hidden_modules_for_settings())
        self.tabs.open_tab(self._sidebar_settings_page, "🧭 Sidebar Ayarlari")

    def open_company_settings(self):
        if self._company_profile_page is None:
            self._company_profile_page = CompanyProfilePage()
        self.tabs.open_tab(self._company_profile_page, "🏢 Company Profile")

    def open_users(self):
        self.tabs.open_tab(PlaceholderPage("Kullanicilar"), "👤 Kullanicilar")

    def open_authorization(self):
        self.tabs.open_tab(PlaceholderPage("Yetkilendirme"), "🛡 Yetkilendirme")

    def open_currency_rates(self):
        self.tabs.open_tab(PlaceholderPage("Doviz Kurlari"), "💱 Doviz Kurlari")

    def open_backup(self):
        self.tabs.open_tab(PlaceholderPage("Yedekleme"), "🗄 Yedekleme")
