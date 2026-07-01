from __future__ import annotations

from PySide6.QtCore import QEasingCurve, Property, QPropertyAnimation, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QPushButton,
    QStyle,
    QWidget,
)

from shared.ui_theme import THEME


class ActionButton(QPushButton):
    def __init__(self, text: str, role: str, icon_key: str, parent=None):
        super().__init__(text, parent)
        self.setProperty("role", role)
        self.setMinimumHeight(THEME.BUTTON_HEIGHT)
        self.setMinimumWidth(126)
        self.setCursor(Qt.PointingHandCursor)

        icon = _resolve_icon(self.style(), icon_key)
        if not icon.isNull():
            self.setIcon(icon)

        self._glow = QGraphicsDropShadowEffect(self)
        self._glow.setBlurRadius(0)
        self._glow.setOffset(0, 0)
        self._glow.setColor(QColor("#00000000"))
        self.setGraphicsEffect(self._glow)

        self._blur = 0.0
        self._anim = QPropertyAnimation(self, b"glowBlur", self)
        self._anim.setDuration(160)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)

    def enterEvent(self, event):  # noqa: N802
        self._animate_glow(14.0)
        return super().enterEvent(event)

    def leaveEvent(self, event):  # noqa: N802
        self._animate_glow(0.0)
        return super().leaveEvent(event)

    def mousePressEvent(self, event):  # noqa: N802
        self._animate_glow(8.0)
        return super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):  # noqa: N802
        self._animate_glow(14.0 if self.underMouse() else 0.0)
        return super().mouseReleaseEvent(event)

    def _animate_glow(self, value: float) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._blur)
        self._anim.setEndValue(value)
        self._anim.start()

    def _get_glow_blur(self) -> float:
        return self._blur

    def _set_glow_blur(self, value: float) -> None:
        self._blur = float(value)
        radius = max(0.0, self._blur)
        self._glow.setBlurRadius(radius)
        alpha = min(150, int(radius * 7))
        self._glow.setColor(QColor(96, 165, 250, alpha))

    glowBlur = Property(float, _get_glow_blur, _set_glow_blur)


class ActionButtonBar(QWidget):
    def __init__(
        self,
        parent=None,
        *,
        include_save_close: bool = True,
        preview_text: str = "Preview",
        save_text: str = "Save",
        save_close_text: str = "Save & Close",
        cancel_text: str = "Cancel",
    ):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 6, 0, 0)
        layout.setSpacing(10)
        layout.addStretch(1)

        self.preview_button = ActionButton(preview_text, "preview", "preview", self)
        self.save_button = ActionButton(save_text, "save", "save", self)
        self.save_close_button = ActionButton(save_close_text, "saveClose", "save_close", self)
        self.cancel_button = ActionButton(cancel_text, "cancel", "cancel", self)

        layout.addWidget(self.preview_button)
        layout.addWidget(self.save_button)
        if include_save_close:
            layout.addWidget(self.save_close_button)
        else:
            self.save_close_button.hide()
        layout.addWidget(self.cancel_button)

    def set_handlers(self, *, on_preview=None, on_save=None, on_save_close=None, on_cancel=None) -> None:
        if on_preview is not None:
            self.preview_button.clicked.connect(on_preview)
        if on_save is not None:
            self.save_button.clicked.connect(on_save)
        if on_save_close is not None:
            self.save_close_button.clicked.connect(on_save_close)
        if on_cancel is not None:
            self.cancel_button.clicked.connect(on_cancel)


def _resolve_icon(style: QStyle, icon_key: str):
    # Use one icon source with theme-first fallback for consistency.
    if icon_key == "preview":
        icon = style.standardIcon(QStyle.SP_FileDialogDetailedView)
        return icon
    if icon_key == "save":
        return style.standardIcon(QStyle.SP_DialogSaveButton)
    if icon_key == "save_close":
        return style.standardIcon(QStyle.SP_DialogApplyButton)
    if icon_key == "cancel":
        return style.standardIcon(QStyle.SP_DialogCancelButton)
    return style.standardIcon(QStyle.SP_FileIcon)
