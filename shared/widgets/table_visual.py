from PySide6.QtCore import Qt
from PySide6.QtWidgets import QAbstractItemView, QLabel, QTableWidget


def apply_list_table_visuals(table: QTableWidget) -> None:
    """Apply consistent MeWa list-table visuals without affecting business logic."""
    table.setAlternatingRowColors(True)
    table.setMouseTracking(True)
    table.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
    table.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
    table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
    table.verticalScrollBar().setSingleStep(14)
    table.horizontalScrollBar().setSingleStep(14)

    table.setStyleSheet(
        ""
        "QTableWidget {"
        "background-color: #111827;"
        "alternate-background-color: #0f172a;"
        "color: #e5e7eb;"
        "gridline-color: #1f2937;"
        "selection-background-color: #2563eb;"
        "selection-color: #ffffff;"
        "border: 1px solid #1f2937;"
        "border-radius: 10px;"
        "}"
        "QTableWidget::item {"
        "padding: 6px;"
        "}"
        "QTableWidget::item:hover {"
        "background-color: #1e293b;"
        "}"
        "QHeaderView::section {"
        "background-color: #1f2937;"
        "color: #e5e7eb;"
        "padding: 8px 6px;"
        "font-weight: 600;"
        "border: 1px solid #111827;"
        "}"
        "QTableCornerButton::section {"
        "background-color: #1f2937;"
        "border: 1px solid #111827;"
        "}"
        "QScrollBar:vertical, QScrollBar:horizontal {"
        "background: #0f172a;"
        "border: none;"
        "}"
        "QScrollBar::handle:vertical, QScrollBar::handle:horizontal {"
        "background: #334155;"
        "border-radius: 4px;"
        "min-height: 24px;"
        "min-width: 24px;"
        "}"
        "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,"
        "QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {"
        "width: 0px;"
        "height: 0px;"
        "}"
        ""
    )


def create_record_count_label() -> QLabel:
    label = QLabel("Toplam Kayıt: 0")
    label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
    label.setStyleSheet("font-size: 12px; color: #94a3b8; padding: 4px 2px;")
    return label


def set_record_count(label: QLabel, count: int) -> None:
    label.setText(f"Toplam Kayıt: {count}")
