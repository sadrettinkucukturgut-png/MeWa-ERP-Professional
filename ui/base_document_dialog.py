from PySide6.QtWidgets import QDialog

from shared.widgets.action_button_bar import ActionButtonBar


class BaseDocumentDialog(QDialog):
    """Base dialog marker for all commercial document dialogs."""

    document_label = "Belge"

    def create_standard_action_bar(self, *, include_save_close: bool = True) -> ActionButtonBar:
        bar = ActionButtonBar(self, include_save_close=include_save_close)
        self.preview_btn = bar.preview_button
        self.save_btn = bar.save_button
        self.save_close_btn = bar.save_close_button
        self.cancel_btn = bar.cancel_button
        return bar
