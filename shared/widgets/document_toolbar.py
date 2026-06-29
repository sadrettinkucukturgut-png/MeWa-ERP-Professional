from typing import Any, Callable, Dict

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu, QTableWidget, QToolBar, QWidget

from services.document_export_service import DocumentExportService, payload_from_provider
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
        self.action_whatsapp = QAction("💬 WhatsApp", parent)
        self.action_email = QAction("📧 Email", parent)
        self.action_open_file = QAction("📂 Open File", parent)
        self.action_save_as = QAction("💾 Save As", parent)
        self.action_columns = QAction("⚙ Columns", parent)

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
        self.action_whatsapp.triggered.connect(lambda: self.export_service.whatsapp_document(self._payload()))
        self.action_email.triggered.connect(lambda: self.export_service.email_document(self._payload()))
        self.action_open_file.triggered.connect(lambda: self.export_service.open_generated_file_folder(self._payload()))
        self.action_save_as.triggered.connect(lambda: self.export_service.save_as(self._payload()))
        self.action_columns.triggered.connect(self._show_columns_menu)

    def _add_actions(self):
        # Exact standard toolbar order requested by user.
        self.toolbar.addAction(self.action_excel)
        self.toolbar.addAction(self.action_pdf)
        self.toolbar.addAction(self.action_print)
        self.toolbar.addAction(self.action_whatsapp)
        self.toolbar.addAction(self.action_email)
        self.toolbar.addAction(self.action_open_file)
        self.toolbar.addAction(self.action_save_as)
        self.toolbar.addAction(self.action_columns)

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
