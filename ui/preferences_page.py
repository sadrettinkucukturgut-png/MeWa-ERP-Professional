from PySide6.QtCore import Qt
from PySide6.QtWidgets import QCheckBox, QComboBox, QFormLayout, QLabel, QVBoxLayout, QWidget

from services.share_service import ShareService


class PreferencesPage(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("preferencesPage")

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)

        title = QLabel("Preferences")
        title.setStyleSheet("font-size:18px; font-weight:700;")
        root.addWidget(title)

        description = QLabel("Configure default document sharing behavior.")
        description.setStyleSheet("color:#64748b;")
        root.addWidget(description)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignLeft)
        form.setFormAlignment(Qt.AlignTop)

        self.default_share_combo = QComboBox()
        for label, value in ShareService.available_default_methods():
            self.default_share_combo.addItem(label, value)

        self.remember_default_checkbox = QCheckBox("Remember my default sharing method")

        form.addRow("Default Share Method", self.default_share_combo)
        form.addRow("", self.remember_default_checkbox)
        root.addLayout(form)
        root.addStretch(1)

        self._load_settings()
        self.default_share_combo.currentIndexChanged.connect(self._on_default_method_changed)
        self.remember_default_checkbox.toggled.connect(self._on_remember_toggled)

    def _load_settings(self) -> None:
        method = ShareService.get_default_method()
        index = self.default_share_combo.findData(method)
        if index >= 0:
            self.default_share_combo.setCurrentIndex(index)
        self.remember_default_checkbox.setChecked(ShareService.is_remember_default_enabled())

    def _on_default_method_changed(self, _index: int) -> None:
        method = str(self.default_share_combo.currentData() or "").strip()
        if method:
            ShareService.set_default_method(method)

    def _on_remember_toggled(self, checked: bool) -> None:
        ShareService.set_remember_default_enabled(bool(checked))
