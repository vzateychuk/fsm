"""DocumentsService — list and delete indexed knowledge-base documents."""
from __future__ import annotations

import logging

from dataclasses import dataclass

from src.services.errors import NotFoundError
from src.store.knowledge_store import DocumentMetadata, KnowledgeStore

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class DocumentDetail:
    metadata: DocumentMetadata
    content: str


class DocumentsService:
    """Application service for document catalog operations outside the ingest pipeline."""

    def __init__(self, knowledge_store: KnowledgeStore) -> None:
        self._knowledge_store = knowledge_store

    async def list_documents(self) -> list[DocumentMetadata]:
        """Return all indexed documents ordered by upload time descending."""
        return await self._knowledge_store.list_documents_by_date(limit=500)

    async def get_document(self, document_id: str) -> DocumentDetail | None:
        """Retrieve a single document with metadata and raw text by ID.

        Returns:
            DocumentDetail if found, None if not found.
        """
        metadata = await self._knowledge_store.get_document_metadata(document_id)
        if metadata is None:
            return None

        raw_texts = await self._knowledge_store.get_documents_raw_text([document_id])
        content = raw_texts.get(document_id)
        if content is None:
            return None

        return DocumentDetail(metadata=metadata, content=content)

    async def delete_document(self, document_id: str) -> None:
        """Delete an indexed document, its chunks, and FTS entries.

        Raises:
            NotFoundError: If the document does not exist.
        """
        doc = await self._knowledge_store.get_document_metadata(document_id)
        if doc is None:
            raise NotFoundError(f"Document {document_id!r} not found")

        deleted = await self._knowledge_store.delete_document(document_id)
        if not deleted:
            raise NotFoundError(f"Document {document_id!r} not found")

        logger.info("Deleted document: %s (source_path=%s)", document_id, doc.source_path)
