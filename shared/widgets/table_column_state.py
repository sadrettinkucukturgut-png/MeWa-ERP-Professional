from typing import Optional

from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QHeaderView, QTableView, QToolBar, QWidget


def apply_table_column_standard(
    table: QTableView,
    settings: QSettings,
    settings_key_prefix: str,
    keep_last_column_stretch: bool = False,
) -> None:
    """Apply MeWa table behavior: resize, autosize, order and persistent layout state."""
    header = table.horizontalHeader()

    table.setSortingEnabled(True)
    table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
    header.setSectionsClickable(True)

    _restore_widths(table, settings, settings_key_prefix)
    _restore_column_order(header, settings, settings_key_prefix)
    _apply_lock_state(table, settings, settings_key_prefix, keep_last_column_stretch)

    header.sectionResized.connect(
        lambda logical_index, old_size, new_size: _save_width(
            settings, settings_key_prefix, logical_index, new_size
        )
    )

    header.sectionMoved.connect(
        lambda logical_index, old_visual_index, new_visual_index: _save_column_order(
            header, settings, settings_key_prefix
        )
    )

    header.sectionHandleDoubleClicked.connect(
        lambda logical_index: _autosize_and_save(table, settings, settings_key_prefix, logical_index)
    )


def add_layout_lock_toggle(
    toolbar: QToolBar,
    table: QTableView,
    settings: QSettings,
    settings_key_prefix: str,
    parent: Optional[QWidget] = None,
    keep_last_column_stretch: bool = False,
) -> QAction:
    action = QAction(parent)
    action.setCheckable(True)

    initial_locked = _read_locked(settings, settings_key_prefix)
    action.setChecked(initial_locked)
    _update_lock_action_text(action, initial_locked)

    def _toggle_layout_lock(checked: bool) -> None:
        _save_locked(settings, settings_key_prefix, checked)
        _apply_lock_state(table, settings, settings_key_prefix, keep_last_column_stretch)
        _update_lock_action_text(action, checked)

    action.toggled.connect(_toggle_layout_lock)
    toolbar.addAction(action)
    return action


def _width_key(prefix: str, logical_index: int) -> str:
    return f"{prefix}/width/{logical_index}"


def _restore_widths(table: QTableView, settings: QSettings, prefix: str) -> None:
    for column_index in range(table.model().columnCount()):
        width_value = settings.value(_width_key(prefix, column_index), None)
        if width_value is None:
            continue
        try:
            table.setColumnWidth(column_index, int(width_value))
        except (TypeError, ValueError):
            continue


def _save_width(settings: QSettings, prefix: str, logical_index: int, width: int) -> None:
    settings.setValue(_width_key(prefix, logical_index), int(width))


def _autosize_and_save(table: QTableView, settings: QSettings, prefix: str, logical_index: int) -> None:
    if _read_locked(settings, prefix):
        return
    table.resizeColumnToContents(logical_index)
    _save_width(settings, prefix, logical_index, table.columnWidth(logical_index))


def _order_key(prefix: str) -> str:
    return f"{prefix}/order"


def _lock_key(prefix: str) -> str:
    return f"{prefix}/layout_locked"


def _save_column_order(header: QHeaderView, settings: QSettings, prefix: str) -> None:
    order = [header.logicalIndex(visual_index) for visual_index in range(header.count())]
    settings.setValue(_order_key(prefix), order)


def _restore_column_order(header: QHeaderView, settings: QSettings, prefix: str) -> None:
    saved_value = settings.value(_order_key(prefix), None)
    if not isinstance(saved_value, list):
        return

    try:
        saved_order = [int(value) for value in saved_value]
    except (TypeError, ValueError):
        return

    expected = list(range(header.count()))
    if sorted(saved_order) != expected:
        return

    for target_visual_index, logical_index in enumerate(saved_order):
        current_visual_index = header.visualIndex(logical_index)
        if current_visual_index != target_visual_index:
            header.moveSection(current_visual_index, target_visual_index)


def _read_locked(settings: QSettings, prefix: str) -> bool:
    return str(settings.value(_lock_key(prefix), "false")).lower() == "true"


def _save_locked(settings: QSettings, prefix: str, locked: bool) -> None:
    settings.setValue(_lock_key(prefix), bool(locked))


def _update_lock_action_text(action: QAction, locked: bool) -> None:
    action.setText("🔓 Düzeni Aç" if locked else "🔒 Düzeni Kilitle")


def _apply_lock_state(
    table: QTableView,
    settings: QSettings,
    prefix: str,
    keep_last_column_stretch: bool,
) -> None:
    header = table.horizontalHeader()
    locked = _read_locked(settings, prefix)

    if locked:
        header.setSectionResizeMode(QHeaderView.Fixed)
        header.setSectionsMovable(False)
    else:
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setSectionsMovable(True)

    header.setStretchLastSection(keep_last_column_stretch)
