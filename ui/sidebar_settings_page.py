from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class SidebarSettingsPage(QWidget):
    showHiddenRequested = Signal()
    moduleVisibilityChanged = Signal(str, bool)
    resetRequested = Signal()

    def __init__(self, hidden_modules: list[tuple[str, str]]):
        super().__init__()
        self.setObjectName("sidebarSettingsPage")

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)

        title = QLabel("Sidebar Settings")
        title.setStyleSheet("font-size:18px; font-weight:700;")
        root.addWidget(title)

        description = QLabel(
            "Hidden modules are not deleted. Re-enable any module below."
        )
        description.setStyleSheet("color:#64748b;")
        root.addWidget(description)

        toolbar = QHBoxLayout()
        self.btn_show_hidden = QPushButton("Show Hidden Modules")
        self.btn_reset_layout = QPushButton("Reset Sidebar Layout")
        toolbar.addWidget(self.btn_show_hidden)
        toolbar.addWidget(self.btn_reset_layout)
        toolbar.addStretch(1)
        root.addLayout(toolbar)

        self.hidden_list = QListWidget()
        self.hidden_list.setSelectionMode(QListWidget.NoSelection)
        root.addWidget(self.hidden_list, 1)

        self.btn_show_hidden.clicked.connect(self.showHiddenRequested.emit)
        self.btn_reset_layout.clicked.connect(self._confirm_reset)

        self.set_hidden_modules(hidden_modules)

    def set_hidden_modules(self, hidden_modules: list[tuple[str, str]]) -> None:
        try:
            self.hidden_list.itemChanged.disconnect(self._on_hidden_item_changed)
        except Exception:
            pass
        self.hidden_list.blockSignals(True)
        self.hidden_list.clear()
        for module_id, title in hidden_modules:
            item = QListWidgetItem(title)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            item.setData(Qt.UserRole, module_id)
            self.hidden_list.addItem(item)
        self.hidden_list.blockSignals(False)
        self.hidden_list.itemChanged.connect(self._on_hidden_item_changed)

    def _on_hidden_item_changed(self, item: QListWidgetItem) -> None:
        module_id = item.data(Qt.UserRole)
        if not module_id:
            return
        should_be_hidden = item.checkState() != Qt.Checked
        self.moduleVisibilityChanged.emit(str(module_id), should_be_hidden)

    def _confirm_reset(self) -> None:
        answer = QMessageBox.question(
            self,
            "Reset Sidebar Layout",
            "Reset sidebar layout to default order, visibility, and width?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer == QMessageBox.Yes:
            self.resetRequested.emit()
