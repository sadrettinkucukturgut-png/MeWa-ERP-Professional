from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu, QWidget


@dataclass
class ListContextMenuAction:
    text: str
    handler: Optional[Callable[[], None]] = None
    enabled: bool = True
    separator_before: bool = False


class ListContextMenuBuilder:
    """Reusable right-click menu builder for ERP list pages."""

    def __init__(self, parent: QWidget):
        self.parent = parent

    def build(self, actions: list[ListContextMenuAction]) -> QMenu:
        menu = QMenu(self.parent)
        for item in actions:
            if item.separator_before and menu.actions():
                menu.addSeparator()
            action = QAction(item.text, self.parent)
            action.setEnabled(item.enabled)
            if item.handler is not None:
                action.triggered.connect(item.handler)
            menu.addAction(action)
        return menu