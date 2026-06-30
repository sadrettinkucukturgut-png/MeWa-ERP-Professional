from typing import Any, Callable, Dict

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu, QTableWidget, QToolBar, QToolButton, QWidget, QWidgetAction

from services.document_export_service import DocumentExportService, payload_from_provider
from services.share_service import ShareMethod, ShareService
from shared.widgets.table_column_state import add_layout_lock_toggle


class DocumentToolbar:
    """Reusable standard document toolbar for all business document modules."""

    def __init__(
        self,
        *,
        parent: QWidget,
        toolbar: QToolBar,
        table: QTableWidget,
        settings,
        layout_key: str,
        payload_provider: Callable[[], Dict[str, Any]],
    ):
        self.parent = parent
        self.toolbar = toolbar
        self.table = table
        self.settings = settings
        self.layout_key = layout_key
        self.payload_provider = payload_provider
        self.export_service = DocumentExportService(parent)

        self.action_excel = QAction("📄 Excel", parent)
        self.action_pdf = QAction("📄 PDF", parent)
        self.action_print = QAction("🖨 Print", parent)
        self.action_email = QAction("📧 Email", parent)
        self.action_open_file = QAction("📂 Open File", parent)
        self.action_save_as = QAction("💾 Save As", parent)
        self.action_columns = QAction("⚙ Columns", parent)

        self.share_button = QToolButton(parent)
        self.share_button.setText("Share")
        self.share_button.setPopupMode(QToolButton.MenuButtonPopup)
        self.share_button.clicked.connect(self._share_with_default)
        self.share_menu = QMenu(parent)
        self.share_button.setMenu(self.share_menu)
        self.share_widget_action = QWidgetAction(parent)
        self.share_widget_action.setDefaultWidget(self.share_button)

        self._wire_actions()
        self._add_actions()

        self.action_layout_lock = add_layout_lock_toggle(
            self.toolbar,
            self.table,
            self.settings,
            self.layout_key,
            self.parent,
            keep_last_column_stretch=False,
        )
        self.action_layout_lock.setText("🔒 Lock Layout")
        self.action_layout_lock.toggled.connect(self._on_lock_toggled)

    def _payload(self):
        return payload_from_provider(self.payload_provider)

    def _wire_actions(self):
        self.action_excel.triggered.connect(lambda: self.export_service.export_excel(self._payload()))
        self.action_pdf.triggered.connect(lambda: self.export_service.export_pdf(self._payload()))
        self.action_print.triggered.connect(lambda: self.export_service.print_document(self._payload()))
        self.action_email.triggered.connect(lambda: self.export_service.email_document(self._payload()))
        self.action_open_file.triggered.connect(lambda: self.export_service.open_generated_file_folder(self._payload()))
        self.action_save_as.triggered.connect(lambda: self.export_service.save_as(self._payload()))
        self.action_columns.triggered.connect(self._show_columns_menu)

        self._build_share_menu()

    def _add_actions(self):
        # Exact standard toolbar order requested by user.
        self.toolbar.addAction(self.action_excel)
        self.toolbar.addAction(self.action_pdf)
        self.toolbar.addAction(self.action_print)
        self.toolbar.addAction(self.share_widget_action)
        self.toolbar.addAction(self.action_email)
        self.toolbar.addAction(self.action_open_file)
        self.toolbar.addAction(self.action_save_as)
        self.toolbar.addAction(self.action_columns)

    def _build_share_menu(self):
        self.share_menu.clear()

        self.action_share_wa_desktop = self.share_menu.addAction("WhatsApp Desktop")
        self.action_share_wa_web = self.share_menu.addAction("WhatsApp Web")
        self.action_share_email = self.share_menu.addAction("Email")
        self.action_share_open_folder = self.share_menu.addAction("Open PDF Folder")
        self.action_share_copy_path = self.share_menu.addAction("Copy PDF Path")

        self.share_menu.addSeparator()
        disabled_labels = ["Microsoft Teams", "Telegram", "Google Drive", "OneDrive", "Dropbox", "FTP"]
        for label in disabled_labels:
            action = self.share_menu.addAction(label)
            action.setEnabled(False)

        self.share_menu.addSeparator()
        self.action_remember_default = self.share_menu.addAction("Remember my default sharing method")
        self.action_remember_default.setCheckable(True)
        self.action_remember_default.setChecked(ShareService.is_remember_default_enabled())
        self.action_remember_default.toggled.connect(ShareService.set_remember_default_enabled)

        self.action_share_wa_desktop.triggered.connect(lambda: self._share_with_method(ShareMethod.WHATSAPP_DESKTOP))
        self.action_share_wa_web.triggered.connect(lambda: self._share_with_method(ShareMethod.WHATSAPP_WEB))
        self.action_share_email.triggered.connect(lambda: self._share_with_method(ShareMethod.EMAIL))
        self.action_share_open_folder.triggered.connect(lambda: self._share_with_method(ShareMethod.OPEN_FOLDER))
        self.action_share_copy_path.triggered.connect(lambda: self._share_with_method(ShareMethod.COPY_PDF_PATH))

    def _share_with_default(self):
        method = ShareService.get_default_method()
        self._share_with_method(method)

    def _share_with_method(self, method: str):
        payload = self._payload()
        ok = self.export_service.share_document(payload, method=method)
        if ok and ShareService.is_remember_default_enabled():
            ShareService.set_default_method(method)

    def _show_columns_menu(self):
        menu = QMenu(self.parent)
        for index in range(self.table.columnCount()):
            label = self.table.horizontalHeaderItem(index).text() if self.table.horizontalHeaderItem(index) else str(index)
            action = QAction(label, self.parent)
            action.setCheckable(True)
            action.setChecked(not self.table.isColumnHidden(index))
            action.triggered.connect(lambda checked, col=index: self.table.setColumnHidden(col, not checked))
            menu.addAction(action)

        menu.addSeparator()
        reset_action = QAction("Reset To Default", self.parent)
        reset_action.triggered.connect(self._reset_columns)
        menu.addAction(reset_action)

        menu.exec_(self.toolbar.mapToGlobal(self.toolbar.rect().bottomLeft()))

    def _reset_columns(self):
        header = self.table.horizontalHeader()
        for col in range(self.table.columnCount()):
            self.table.setColumnHidden(col, False)
        for visual_index, logical_index in enumerate(range(self.table.columnCount())):
            current_visual = header.visualIndex(logical_index)
            if current_visual != visual_index:
                header.moveSection(current_visual, visual_index)
        self.table.resizeColumnsToContents()

    def _on_lock_toggled(self, checked: bool):
        self.action_layout_lock.setText("🔓 Unlock Layout" if checked else "🔒 Lock Layout")

    def add_extension_action(self, text: str, handler):
        """Allow future enterprise actions (EDI, SharePoint, cloud drives, signatures)."""
        action = QAction(text, self.parent)
        action.triggered.connect(handler)
        self.toolbar.addAction(action)
        return action
