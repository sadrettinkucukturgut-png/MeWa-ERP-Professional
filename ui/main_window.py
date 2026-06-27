from PySide6.QtCore import QSettings, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QSplitter,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.tab_manager import TabManager
from shared.app_assets import get_company_logo_icon, get_scaled_company_logo
from ui.cari_hareketleri_dialog import CariHareketleriDialog
from ui.cari_list_page import CariListPage
from ui.dashboard_page import DashboardPage
from ui.goods_receipt_page import GoodsReceiptPage
from ui.purchase_invoice_page import PurchaseInvoicePage
from ui.purchase_order_page import PurchaseOrderPage
from ui.sidebar_settings_page import SidebarSettingsPage
from ui.stock_list_page import StockListPage


ROLE_KIND = Qt.UserRole + 1
ROLE_MODULE_ID = Qt.UserRole + 2
ROLE_SUBMENU_ID = Qt.UserRole + 3
ROLE_TEXT_FULL = Qt.UserRole + 4
ROLE_TEXT_ICON = Qt.UserRole + 5

KIND_MODULE = "module"
KIND_SUBMENU = "submenu"

FAVORITES_MODULE_ID = "__favorites__"


class SidebarTreeWidget(QTreeWidget):
    orderChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
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
        if current.parent() is not None:
            return
        super().startDrag(supported_actions)

    def dropEvent(self, event):  # noqa: N802
        source_item = self.currentItem()
        if source_item is None or source_item.parent() is not None:
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
        self._hidden_module_ids = set()
        self._favorite_submenu_ids = []
        self._expanded_module_ids = set()
        self._suppress_sidebar_state_save = False
        self._sidebar_settings_page = None

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

        watermark_row = QHBoxLayout()
        watermark_row.setContentsMargins(0, 0, 0, 0)
        watermark_row.addStretch()

        self.logo_watermark = QLabel()
        self.logo_watermark.setObjectName("logoWatermark")
        self.logo_watermark.setStyleSheet("padding: 4px; background: transparent;")
        watermark_row.addWidget(self.logo_watermark, alignment=Qt.AlignRight | Qt.AlignBottom)
        content_layout.addLayout(watermark_row)
        self._update_logo_watermark()

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
                    {"id": "categories", "label": "🗂 Kategoriler", "callback": self.open_stock_categories},
                    {"id": "warehouses", "label": "🏬 Depolar", "callback": self.open_stock_warehouses},
                    {"id": "brands", "label": "🏷 Markalar", "callback": self.open_stock_brands},
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
                "title": "Satis",
                "items": [
                    {"id": "quotes", "label": "📝 Teklifler", "callback": self.open_sales_quotes},
                    {"id": "proforma", "label": "📄 Proforma", "callback": self.open_sales_proforma},
                    {"id": "orders", "label": "🧾 Satis Siparisleri", "callback": self.open_sales_orders},
                    {"id": "invoices", "label": "🧾 Satis Faturalari", "callback": self.open_sales_invoices},
                    {"id": "reports", "label": "📊 Satis Raporlari", "callback": self.open_sales_reports},
                ],
            },
            {
                "id": "finans",
                "icon": "🏦",
                "title": "Finans",
                "items": [
                    {"id": "cash", "label": "💵 Kasa", "callback": self.open_cash},
                    {"id": "bank", "label": "🏦 Banka", "callback": self.open_bank},
                    {"id": "checks", "label": "🧾 Cek / Senet", "callback": self.open_checks},
                    {"id": "reports", "label": "📊 Finans Raporlari", "callback": self.open_finance_reports},
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
                    {"id": "company", "label": "🏢 Firma Bilgileri", "callback": self.open_company_settings},
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

        hidden = self._read_list_setting("sidebar/layout/hidden_modules")
        self._hidden_module_ids = {module_id for module_id in hidden if module_id in self._module_catalog}

        favorites = self._read_list_setting("sidebar/layout/favorites")
        self._favorite_submenu_ids = []
        for submenu_id in favorites:
            if submenu_id in self._submenu_catalog and submenu_id not in self._favorite_submenu_ids:
                self._favorite_submenu_ids.append(submenu_id)

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
        self.ui_settings.setValue("sidebar/layout/hidden_modules", sorted(self._hidden_module_ids))
        self.ui_settings.setValue("sidebar/layout/favorites", self._favorite_submenu_ids)
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
                if not self._favorite_submenu_ids:
                    continue
                module_item = self._create_module_item(FAVORITES_MODULE_ID, "⭐ Favorites")
                for submenu_id in self._favorite_submenu_ids:
                    submenu = self._submenu_catalog.get(submenu_id)
                    if submenu is None:
                        continue
                    child = self._create_submenu_item(submenu_id, f"⭐ {submenu['label']}")
                    module_item.addChild(child)
                self.sidebar_tree.addTopLevelItem(module_item)
                module_item.setExpanded(FAVORITES_MODULE_ID in self._expanded_module_ids)
                continue

            module = self._module_catalog.get(module_id)
            if module is None:
                continue

            module_label = f"{module['icon']}  {module['title']}"
            module_item = self._create_module_item(module_id, module_label)
            for item in module["items"]:
                submenu_id = self._submenu_key(module_id, item["id"])
                child = self._create_submenu_item(submenu_id, item["label"])
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
            | Qt.ItemIsDragEnabled
        )
        return item

    def _create_submenu_item(self, submenu_id: str, full_text: str) -> QTreeWidgetItem:
        item = QTreeWidgetItem([full_text])
        icon_only = full_text.split(" ", 1)[0]
        item.setData(0, ROLE_KIND, KIND_SUBMENU)
        item.setData(0, ROLE_SUBMENU_ID, submenu_id)
        item.setData(0, ROLE_TEXT_FULL, full_text)
        item.setData(0, ROLE_TEXT_ICON, icon_only)
        item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
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
                hide_action = menu.addAction("Hide Module")
                hide_action.setEnabled(not self.sidebar_locked)
                hide_action.triggered.connect(lambda: self._set_module_hidden(module_id, True))

            expand_action = menu.addAction("Expand" if not item.isExpanded() else "Collapse")
            expand_action.triggered.connect(lambda: item.setExpanded(not item.isExpanded()))

            if module_id == FAVORITES_MODULE_ID:
                clear_favorites = menu.addAction("Clear Favorites")
                clear_favorites.setEnabled((not self.sidebar_locked) and bool(self._favorite_submenu_ids))
                clear_favorites.triggered.connect(self._clear_favorites)

        elif kind == KIND_SUBMENU:
            submenu_id = str(item.data(0, ROLE_SUBMENU_ID))
            is_favorite = submenu_id in self._favorite_submenu_ids

            if is_favorite:
                unpin_action = menu.addAction("Remove from Favorites")
                unpin_action.setEnabled(not self.sidebar_locked)
                unpin_action.triggered.connect(lambda: self._set_favorite(submenu_id, False))
            else:
                pin_action = menu.addAction("Pin to Favorites")
                pin_action.setEnabled(not self.sidebar_locked)
                pin_action.triggered.connect(lambda: self._set_favorite(submenu_id, True))

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

    def _on_sidebar_settings_visibility_changed(self, module_id: str, hidden: bool) -> None:
        self._set_module_hidden(module_id, hidden)

    def _reset_sidebar_layout(self) -> None:
        self._module_order = self._default_module_order()
        self._hidden_module_ids.clear()
        self._favorite_submenu_ids = []
        self._expanded_module_ids = {"dashboard"}
        self.sidebar_is_expanded = True
        self.sidebar_locked = False
        self.sidebar_expanded_width = 260

        self._rebuild_sidebar_tree()
        self._apply_sidebar_width_state()
        self._set_sidebar_locked(False, save=False)
        self._update_sidebar_text_mode()
        self._save_sidebar_layout_state()

    def _set_favorite(self, submenu_id: str, enabled: bool) -> None:
        if submenu_id not in self._submenu_catalog:
            return

        if enabled:
            if submenu_id not in self._favorite_submenu_ids:
                self._favorite_submenu_ids.append(submenu_id)
            if FAVORITES_MODULE_ID not in self._module_order:
                self._module_order.insert(0, FAVORITES_MODULE_ID)
            self._expanded_module_ids.add(FAVORITES_MODULE_ID)
        else:
            self._favorite_submenu_ids = [
                item_id for item_id in self._favorite_submenu_ids if item_id != submenu_id
            ]
            if not self._favorite_submenu_ids:
                self._expanded_module_ids.discard(FAVORITES_MODULE_ID)

        self._rebuild_sidebar_tree()
        self._save_sidebar_layout_state()

    def _clear_favorites(self) -> None:
        self._favorite_submenu_ids = []
        self._expanded_module_ids.discard(FAVORITES_MODULE_ID)
        self._rebuild_sidebar_tree()
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

    def _update_logo_watermark(self):
        width = max(120, min(self.width() // 7, 220))
        height = max(40, min(self.height() // 12, 90))
        pixmap = get_scaled_company_logo(width, height)
        self.logo_watermark.setPixmap(pixmap)

    def resizeEvent(self, event):  # noqa: N802
        super().resizeEvent(event)
        self._update_logo_watermark()

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

    def open_sales_quotes(self):
        self.tabs.open_tab(PlaceholderPage("Teklifler"), "📝 Teklifler")

    def open_sales_proforma(self):
        self.tabs.open_tab(PlaceholderPage("Proforma"), "📄 Proforma")

    def open_sales_orders(self):
        self.tabs.open_tab(PlaceholderPage("Satis Siparisleri"), "🧾 Satis Siparisleri")

    def open_sales_delivery_notes(self):
        self.tabs.open_tab(PlaceholderPage("Satis Irsaliyeleri"), "🚚 Irsaliyeler")

    def open_sales_invoices(self):
        self.tabs.open_tab(PlaceholderPage("Satis Faturalari"), "🧾 Satis Faturalari")

    def open_sales_reports(self):
        self.tabs.open_tab(PlaceholderPage("Satis Raporlari"), "📊 Satis Raporlari")

    def open_cash(self):
        self.tabs.open_tab(PlaceholderPage("Kasa"), "💵 Kasa")

    def open_bank(self):
        self.tabs.open_tab(PlaceholderPage("Banka"), "🏦 Banka")

    def open_checks(self):
        self.tabs.open_tab(PlaceholderPage("Cek / Senet"), "🧾 Cek / Senet")

    def open_finance_reports(self):
        self.tabs.open_tab(PlaceholderPage("Finans Raporlari"), "📊 Finans Raporlari")

    def open_reports(self):
        self.tabs.open_tab(PlaceholderPage("Genel Raporlar"), "📊 Genel Raporlar")

    def open_dashboard_analytics(self):
        self.tabs.open_tab(PlaceholderPage("Dashboard Analizleri"), "📉 Dashboard Analizleri")

    def open_settings(self):
        self.tabs.open_tab(PlaceholderPage("Ayarlar"), "⚙ Ayarlar")

    def open_sidebar_settings(self):
        if self._sidebar_settings_page is None:
            self._sidebar_settings_page = SidebarSettingsPage(self._hidden_modules_for_settings())
            self._sidebar_settings_page.showHiddenRequested.connect(self._show_hidden_modules)
            self._sidebar_settings_page.moduleVisibilityChanged.connect(self._on_sidebar_settings_visibility_changed)
            self._sidebar_settings_page.resetRequested.connect(self._reset_sidebar_layout)
        else:
            self._sidebar_settings_page.set_hidden_modules(self._hidden_modules_for_settings())
        self.tabs.open_tab(self._sidebar_settings_page, "🧭 Sidebar Ayarlari")

    def open_company_settings(self):
        self.tabs.open_tab(PlaceholderPage("Firma Bilgileri"), "🏢 Firma Bilgileri")

    def open_users(self):
        self.tabs.open_tab(PlaceholderPage("Kullanicilar"), "👤 Kullanicilar")

    def open_authorization(self):
        self.tabs.open_tab(PlaceholderPage("Yetkilendirme"), "🛡 Yetkilendirme")

    def open_currency_rates(self):
        self.tabs.open_tab(PlaceholderPage("Doviz Kurlari"), "💱 Doviz Kurlari")

    def open_backup(self):
        self.tabs.open_tab(PlaceholderPage("Yedekleme"), "🗄 Yedekleme")
