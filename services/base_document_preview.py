from __future__ import annotations

from services.document_preview_engine import DocumentPreviewWindow, DocumentTemplate


class BaseDocumentPreview:
    """Small wrapper used by document dialogs/pages to open preview windows."""

    @staticmethod
    def open_preview(template: DocumentTemplate, parent=None) -> DocumentPreviewWindow:
        window = DocumentPreviewWindow(template=template, parent=parent)
        window.show()
        window.raise_()
        window.activateWindow()
        return window
