from __future__ import annotations

from PySide6.QtCore import QMimeData, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QAction, QDesktopServices, QDragEnterEvent, QDropEvent, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTabWidget,
    QTextEdit,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from models.company_profile_model import CompanyProfileModel


class ImageDropLabel(QLabel):
    fileDropped = Signal(str)

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self._title = title
        self.setAcceptDrops(True)
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumHeight(180)
        self.setStyleSheet(
            "QLabel {"
            "border:1px dashed #475569;"
            "border-radius:10px;"
            "background:#0f172a;"
            "color:#94a3b8;"
            "padding:10px;"
            "}"
        )
        self.setText(f"Drop {title} here")

    def dragEnterEvent(self, event: QDragEnterEvent):  # noqa: N802
        if self._extract_local_file(event.mimeData()):
            event.acceptProposedAction()
            return
        event.ignore()

    def dropEvent(self, event: QDropEvent):  # noqa: N802
        file_path = self._extract_local_file(event.mimeData())
        if not file_path:
            event.ignore()
            return
        self.fileDropped.emit(file_path)
        event.acceptProposedAction()

    @staticmethod
    def _extract_local_file(mime_data: QMimeData) -> str:
        if mime_data is None or not mime_data.hasUrls():
            return ""
        for url in mime_data.urls():
            if not url.isLocalFile():
                continue
            path = str(url.toLocalFile() or "").strip()
            if path:
                return path
        return ""


class BrandingAssetCard(QGroupBox):
    assetChanged = Signal(str)

    def __init__(self, *, title: str, asset_type: str, parent=None):
        super().__init__(title, parent)
        self.asset_type = asset_type
        self._stored_path = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        self.preview = ImageDropLabel(title)
        self.preview.fileDropped.connect(self._replace_with_file)
        layout.addWidget(self.preview)

        actions = QHBoxLayout()
        actions.setSpacing(8)

        self.btn_preview = QPushButton("Preview")
        self.btn_replace = QPushButton("Replace")
        self.btn_remove = QPushButton("Remove")

        self.btn_preview.clicked.connect(self._preview_asset)
        self.btn_replace.clicked.connect(self._choose_asset)
        self.btn_remove.clicked.connect(self._remove_asset)

        actions.addWidget(self.btn_preview)
        actions.addWidget(self.btn_replace)
        actions.addWidget(self.btn_remove)
        actions.addStretch(1)
        layout.addLayout(actions)

        self._refresh_preview()

    @property
    def stored_path(self) -> str:
        return self._stored_path

    def set_stored_path(self, value: str) -> None:
        self._stored_path = str(value or "").strip()
        self._refresh_preview()

    def _choose_asset(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Image",
            "",
            "Image Files (*.png *.jpg *.jpeg *.bmp *.webp)",
        )
        if not file_path:
            return
        self._replace_with_file(file_path)

    def _replace_with_file(self, file_path: str) -> None:
        try:
            stored = CompanyProfileModel.copy_branding_asset(file_path, self.asset_type)
        except Exception as exc:
            QMessageBox.warning(self, "Warning", str(exc))
            return
        self._stored_path = stored
        self._refresh_preview()
        self.assetChanged.emit(self._stored_path)

    def _remove_asset(self) -> None:
        self._stored_path = ""
        self._refresh_preview()
        self.assetChanged.emit(self._stored_path)

    def _preview_asset(self) -> None:
        resolved = CompanyProfileModel.resolve_path(self._stored_path)
        if not self._stored_path or not resolved.exists():
            QMessageBox.information(self, "Preview", "No image selected.")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(resolved)))

    def _refresh_preview(self) -> None:
        resolved = CompanyProfileModel.resolve_path(self._stored_path)
        if self._stored_path and resolved.exists():
            pixmap = QPixmap(str(resolved))
            if not pixmap.isNull():
                self.preview.setPixmap(
                    pixmap.scaled(
                        320,
                        170,
                        Qt.KeepAspectRatio,
                        Qt.SmoothTransformation,
                    )
                )
                self.preview.setText("")
                return
        self.preview.setPixmap(QPixmap())
        self.preview.setText(f"Drop {self.title()} here")


class CompanyProfilePage(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("companyProfilePage")

        self._loading = False
        self._dirty = False
        self._last_save_ok = True

        self._autosave_timer = QTimer(self)
        self._autosave_timer.setSingleShot(True)
        self._autosave_timer.setInterval(1300)
        self._autosave_timer.timeout.connect(self._autosave)

        CompanyProfileModel.ensure_schema()

        self._build_ui()
        self._connect_change_signals()
        self._load_profile()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(10)

        title = QLabel("Company Profile")
        title.setStyleSheet("font-size:22px; font-weight:700; color:#e2e8f0;")
        root.addWidget(title)

        subtitle = QLabel("Central company information source for all documents, reports and sharing services.")
        subtitle.setStyleSheet("font-size:12px; color:#94a3b8;")
        root.addWidget(subtitle)

        self.toolbar = QToolBar()
        self.toolbar.setMovable(False)
        self.toolbar.setStyleSheet("QToolBar{background:#111827;border:1px solid #334155;border-radius:8px;padding:6px;spacing:8px;}")

        self.action_save = QAction("Save", self)
        self.action_refresh = QAction("Refresh", self)
        self.action_restore = QAction("Restore Default", self)

        self.toolbar.addAction(self.action_save)
        self.toolbar.addAction(self.action_refresh)
        self.toolbar.addAction(self.action_restore)
        root.addWidget(self.toolbar)

        self.status_label = QLabel("Saved")
        self.status_label.setStyleSheet("font-size:12px; color:#22c55e; padding:2px 4px;")
        root.addWidget(self.status_label)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)

        self._build_general_tab()
        self._build_address_tab()
        self._build_bank_tab()
        self._build_branding_tab()

        container = QScrollArea()
        container.setWidgetResizable(True)
        container.setFrameShape(QScrollArea.NoFrame)
        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.addWidget(self.tabs)
        container.setWidget(body)
        root.addWidget(container, 1)

        self.setStyleSheet(
            "QWidget#companyProfilePage{background:#0b1220;}"
            "QTabWidget::pane{border:1px solid #334155; border-radius:10px; background:#0f172a;}"
            "QTabBar::tab{background:#1e293b; color:#cbd5e1; padding:8px 14px; margin-right:4px; border-top-left-radius:8px; border-top-right-radius:8px;}"
            "QTabBar::tab:selected{background:#0f172a; color:#f8fafc;}"
            "QLineEdit,QTextEdit,QComboBox{background:#0b1324; color:#e2e8f0; border:1px solid #334155; border-radius:8px; padding:8px;}"
            "QGroupBox{color:#e2e8f0; border:1px solid #334155; border-radius:10px; margin-top:8px; font-weight:600;}"
            "QGroupBox::title{subcontrol-origin: margin; left:10px; padding:0 4px;}"
            "QPushButton{background:#1e293b; color:#e2e8f0; border:1px solid #475569; border-radius:8px; padding:6px 10px;}"
            "QPushButton:hover{background:#334155;}"
        )

        self.action_save.triggered.connect(self._save_with_feedback)
        self.action_refresh.triggered.connect(self._refresh_requested)
        self.action_restore.triggered.connect(self._restore_defaults)

    def _build_general_tab(self) -> None:
        tab = QWidget()
        layout = QFormLayout(tab)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setHorizontalSpacing(16)
        layout.setVerticalSpacing(10)

        self.company_name_input = QLineEdit()
        self.short_name_input = QLineEdit()
        self.tax_office_input = QLineEdit()
        self.tax_number_input = QLineEdit()
        self.mersis_input = QLineEdit()
        self.trade_registry_input = QLineEdit()
        self.phone_input = QLineEdit()
        self.mobile_input = QLineEdit()
        self.whatsapp_input = QLineEdit()
        self.email_input = QLineEdit()
        self.website_input = QLineEdit()
        self.currency_combo = QComboBox()
        self.currency_combo.addItems(["USD", "EUR", "TRY", "GBP"])

        layout.addRow("Company Name *", self.company_name_input)
        layout.addRow("Short Name", self.short_name_input)
        layout.addRow("Tax Office", self.tax_office_input)
        layout.addRow("Tax Number", self.tax_number_input)
        layout.addRow("MERSIS Number", self.mersis_input)
        layout.addRow("Trade Registry Number", self.trade_registry_input)
        layout.addRow("Phone", self.phone_input)
        layout.addRow("Mobile", self.mobile_input)
        layout.addRow("WhatsApp", self.whatsapp_input)
        layout.addRow("Email", self.email_input)
        layout.addRow("Website", self.website_input)
        layout.addRow("Currency", self.currency_combo)

        self.tabs.addTab(tab, "General Information")

    def _build_address_tab(self) -> None:
        tab = QWidget()
        layout = QFormLayout(tab)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setHorizontalSpacing(16)
        layout.setVerticalSpacing(10)

        self.address_input = QTextEdit()
        self.address_input.setFixedHeight(88)
        self.factory_address_input = QTextEdit()
        self.factory_address_input.setFixedHeight(88)
        self.city_input = QLineEdit()
        self.postal_code_input = QLineEdit()
        self.country_input = QLineEdit()

        layout.addRow("Head Office Address", self.address_input)
        layout.addRow("Factory Address", self.factory_address_input)
        layout.addRow("City", self.city_input)
        layout.addRow("Postal Code", self.postal_code_input)
        layout.addRow("Country", self.country_input)

        self.tabs.addTab(tab, "Addresses")

    def _build_bank_tab(self) -> None:
        tab = QWidget()
        layout = QFormLayout(tab)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setHorizontalSpacing(16)
        layout.setVerticalSpacing(10)

        self.bank_name_input = QLineEdit()
        self.iban_input = QLineEdit()
        self.swift_input = QLineEdit()
        self.bank_currency_combo = QComboBox()
        self.bank_currency_combo.addItems(["USD", "EUR", "TRY", "GBP"])

        layout.addRow("Bank Name", self.bank_name_input)
        layout.addRow("IBAN", self.iban_input)
        layout.addRow("SWIFT", self.swift_input)
        layout.addRow("Currency", self.bank_currency_combo)

        self.tabs.addTab(tab, "Bank Information")

    def _build_branding_tab(self) -> None:
        tab = QWidget()
        tab_layout = QVBoxLayout(tab)
        tab_layout.setContentsMargins(14, 14, 14, 14)
        tab_layout.setSpacing(10)

        splitter = QSplitter(Qt.Horizontal)

        self.logo_card = BrandingAssetCard(title="Company Logo", asset_type="logo")
        self.stamp_card = BrandingAssetCard(title="Company Stamp", asset_type="stamp")
        self.signature_card = BrandingAssetCard(title="Company Signature", asset_type="signature")

        splitter.addWidget(self.logo_card)
        splitter.addWidget(self.stamp_card)
        splitter.addWidget(self.signature_card)
        splitter.setSizes([360, 360, 360])

        tab_layout.addWidget(splitter)
        self.tabs.addTab(tab, "Branding")

    def _connect_change_signals(self) -> None:
        edits = [
            self.company_name_input,
            self.short_name_input,
            self.tax_office_input,
            self.tax_number_input,
            self.mersis_input,
            self.trade_registry_input,
            self.phone_input,
            self.mobile_input,
            self.whatsapp_input,
            self.email_input,
            self.website_input,
            self.city_input,
            self.postal_code_input,
            self.country_input,
            self.bank_name_input,
            self.iban_input,
            self.swift_input,
        ]
        for edit in edits:
            edit.textChanged.connect(self._on_data_changed)

        self.address_input.textChanged.connect(self._on_data_changed)
        self.factory_address_input.textChanged.connect(self._on_data_changed)
        self.currency_combo.currentIndexChanged.connect(self._on_currency_changed)
        self.bank_currency_combo.currentIndexChanged.connect(self._on_bank_currency_changed)

        self.logo_card.assetChanged.connect(self._on_data_changed)
        self.stamp_card.assetChanged.connect(self._on_data_changed)
        self.signature_card.assetChanged.connect(self._on_data_changed)

        self.phone_input.editingFinished.connect(self._format_phone_inputs)
        self.mobile_input.editingFinished.connect(self._format_phone_inputs)
        self.whatsapp_input.editingFinished.connect(self._format_phone_inputs)
        self.iban_input.editingFinished.connect(self._format_iban)

    def _load_profile(self) -> None:
        self._loading = True
        profile = CompanyProfileModel.get_profile()

        self.company_name_input.setText(str(profile.get("company_name") or ""))
        self.short_name_input.setText(str(profile.get("company_short_name") or ""))
        self.tax_office_input.setText(str(profile.get("tax_office") or ""))
        self.tax_number_input.setText(str(profile.get("tax_number") or ""))
        self.mersis_input.setText(str(profile.get("mersis_number") or ""))
        self.trade_registry_input.setText(str(profile.get("trade_registry_number") or ""))
        self.phone_input.setText(str(profile.get("phone") or ""))
        self.mobile_input.setText(str(profile.get("mobile") or ""))
        self.whatsapp_input.setText(str(profile.get("whatsapp") or ""))
        self.email_input.setText(str(profile.get("email") or ""))
        self.website_input.setText(str(profile.get("website") or ""))

        self.address_input.setPlainText(str(profile.get("address") or ""))
        self.factory_address_input.setPlainText(str(profile.get("factory_address") or ""))
        self.city_input.setText(str(profile.get("city") or ""))
        self.postal_code_input.setText(str(profile.get("postal_code") or ""))
        self.country_input.setText(str(profile.get("country") or ""))

        currency = str(profile.get("currency") or "USD")
        idx = self.currency_combo.findText(currency)
        self.currency_combo.setCurrentIndex(idx if idx >= 0 else 0)
        idx_bank = self.bank_currency_combo.findText(currency)
        self.bank_currency_combo.setCurrentIndex(idx_bank if idx_bank >= 0 else 0)

        self.bank_name_input.setText(str(profile.get("bank_name") or ""))
        self.iban_input.setText(str(profile.get("iban") or ""))
        self.swift_input.setText(str(profile.get("swift") or ""))

        self.logo_card.set_stored_path(str(profile.get("logo_path") or ""))
        self.stamp_card.set_stored_path(str(profile.get("stamp_path") or ""))
        self.signature_card.set_stored_path(str(profile.get("signature_path") or ""))

        self._loading = False
        self._dirty = False
        self._set_status("Saved", ok=True)

    def _collect_payload(self) -> dict[str, str]:
        return {
            "company_name": self.company_name_input.text().strip(),
            "company_short_name": self.short_name_input.text().strip(),
            "tax_office": self.tax_office_input.text().strip(),
            "tax_number": self.tax_number_input.text().strip(),
            "mersis_number": self.mersis_input.text().strip(),
            "trade_registry_number": self.trade_registry_input.text().strip(),
            "phone": CompanyProfileModel.format_phone(self.phone_input.text()),
            "mobile": CompanyProfileModel.format_phone(self.mobile_input.text()),
            "whatsapp": CompanyProfileModel.format_phone(self.whatsapp_input.text()),
            "email": self.email_input.text().strip(),
            "website": self.website_input.text().strip(),
            "address": self.address_input.toPlainText().strip(),
            "factory_address": self.factory_address_input.toPlainText().strip(),
            "city": self.city_input.text().strip(),
            "postal_code": self.postal_code_input.text().strip(),
            "country": self.country_input.text().strip(),
            "bank_name": self.bank_name_input.text().strip(),
            "iban": CompanyProfileModel.format_iban(self.iban_input.text()),
            "swift": self.swift_input.text().strip().upper(),
            "currency": self.currency_combo.currentText().strip() or "USD",
            "logo_path": self.logo_card.stored_path,
            "stamp_path": self.stamp_card.stored_path,
            "signature_path": self.signature_card.stored_path,
        }

    def _validate_payload(self, payload: dict[str, str], *, silent: bool = False) -> bool:
        if not payload.get("company_name"):
            if not silent:
                QMessageBox.warning(self, "Validation", "Company Name is mandatory.")
            return False

        if not CompanyProfileModel.is_valid_email(payload.get("email", "")):
            if not silent:
                QMessageBox.warning(self, "Validation", "Please enter a valid email address.")
            return False

        if not CompanyProfileModel.is_valid_website(payload.get("website", "")):
            if not silent:
                QMessageBox.warning(self, "Validation", "Please enter a valid website address.")
            return False
        return True

    def _save(self, *, show_message: bool, autosave: bool) -> bool:
        payload = self._collect_payload()
        if not self._validate_payload(payload, silent=autosave):
            self._last_save_ok = False
            self._set_status("Validation error", ok=False)
            return False

        try:
            CompanyProfileModel.update_profile(payload)
        except Exception as exc:
            self._last_save_ok = False
            self._set_status("Save failed", ok=False)
            if not autosave:
                QMessageBox.critical(self, "Error", str(exc))
            return False

        self._dirty = False
        self._last_save_ok = True
        self._set_status("Saved", ok=True)
        if show_message:
            QMessageBox.information(self, "Success", "Company Profile saved successfully.")
        return True

    def _save_with_feedback(self) -> None:
        self._save(show_message=True, autosave=False)

    def _refresh_requested(self) -> None:
        if self._dirty:
            answer = QMessageBox.question(
                self,
                "Unsaved Changes",
                "There are unsaved changes. Do you want to discard them and refresh?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                return
        self._load_profile()

    def _restore_defaults(self) -> None:
        answer = QMessageBox.question(
            self,
            "Restore Default",
            "Restore Company Profile to default values?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return

        CompanyProfileModel.restore_defaults()
        self._load_profile()
        QMessageBox.information(self, "Success", "Default company profile restored.")

    def _autosave(self) -> None:
        if not self._dirty:
            return
        self._set_status("Auto-saving...", ok=False)
        self._save(show_message=False, autosave=True)

    def _on_data_changed(self, *_args) -> None:
        if self._loading:
            return
        self._dirty = True
        self._set_status("Unsaved changes", ok=False)
        self._autosave_timer.start()

    def _on_currency_changed(self, _index: int) -> None:
        if self._loading:
            return
        if self.bank_currency_combo.currentText() != self.currency_combo.currentText():
            self.bank_currency_combo.blockSignals(True)
            self.bank_currency_combo.setCurrentText(self.currency_combo.currentText())
            self.bank_currency_combo.blockSignals(False)
        self._on_data_changed()

    def _on_bank_currency_changed(self, _index: int) -> None:
        if self._loading:
            return
        if self.currency_combo.currentText() != self.bank_currency_combo.currentText():
            self.currency_combo.blockSignals(True)
            self.currency_combo.setCurrentText(self.bank_currency_combo.currentText())
            self.currency_combo.blockSignals(False)
        self._on_data_changed()

    def _format_phone_inputs(self) -> None:
        for widget in (self.phone_input, self.mobile_input, self.whatsapp_input):
            widget.setText(CompanyProfileModel.format_phone(widget.text()))

    def _format_iban(self) -> None:
        self.iban_input.setText(CompanyProfileModel.format_iban(self.iban_input.text()))

    def _set_status(self, text: str, *, ok: bool) -> None:
        color = "#22c55e" if ok else "#f59e0b"
        self.status_label.setStyleSheet(f"font-size:12px; color:{color}; padding:2px 4px;")
        self.status_label.setText(text)

    def closeEvent(self, event):  # noqa: N802
        if not self._dirty:
            event.accept()
            return

        answer = QMessageBox.question(
            self,
            "Unsaved Changes",
            "Save changes before closing Company Profile?",
            QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
            QMessageBox.Yes,
        )
        if answer == QMessageBox.Cancel:
            event.ignore()
            return
        if answer == QMessageBox.Yes and not self._save(show_message=False, autosave=False):
            event.ignore()
            return
        event.accept()
