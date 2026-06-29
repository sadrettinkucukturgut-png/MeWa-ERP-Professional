from services.document_preview_engine import (
    DocumentLineItem,
    DocumentRenderer,
    DocumentTemplate,
    ProformaRenderer,
    create_renderer,
)


class BaseDocumentRenderer:
    """Renderer entry point for all commercial document templates."""

    @staticmethod
    def create(template: DocumentTemplate):
        return create_renderer(template)


__all__ = [
    "BaseDocumentRenderer",
    "DocumentTemplate",
    "DocumentLineItem",
    "DocumentRenderer",
    "ProformaRenderer",
]
