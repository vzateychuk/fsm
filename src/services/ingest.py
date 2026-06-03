"""IngestService — synchronous document ingestion."""
from __future__ import annotations

import hashlib
import logging
import os
import tempfile
from typing import Any
from uuid import uuid4

from src.store.knowledge_store import DocumentMetadata, KnowledgeStore
from src.services.errors import IngestFailedError

logger = logging.getLogger(__name__)


class IngestService:
    """Application service for synchronous Markdown document ingestion.

    Accepts document content, writes it to a temporary file, runs the ingest
    saga synchronously, and returns the resulting document metadata.

    The temporary file is always cleaned up regardless of outcome.
    """

    def __init__(
        self,
        saga_runner: Any,  # SagaRunner[IngestInput, IngestData]
        knowledge_store: KnowledgeStore,
    ) -> None:
        self._runner = saga_runner
        self._knowledge_store = knowledge_store

    async def ingest_document(self, content: str) -> DocumentMetadata:
        """Save and index a Markdown document synchronously.

        Args:
            content: Markdown document text.

        Returns:
            DocumentMetadata for the indexed document.

        Raises:
            IngestFailedError: If the saga pipeline fails for any reason.
        """
        # Lazy import to keep services domain independent from inner pipeline modules
        from src.pipelines.ingest.models import IngestData, IngestInput

        # Deduplication: return existing document if content hash matches.
        sha256 = hashlib.sha256(content.encode("utf-8")).hexdigest()
        existing = await self._knowledge_store.find_document_by_sha256(sha256)
        if existing is not None:
            logger.info("Duplicate upload detected, returning existing document_id=%s", existing.document_id)
            return existing

        tmp_path: str | None = None
        try:
            fd, tmp_path = tempfile.mkstemp(suffix=".md")
            try:
                os.write(fd, content.encode("utf-8"))
            finally:
                os.close(fd)

            run_id = f"api-ingest-{uuid4().hex[:8]}"
            logger.info("Starting ingest run_id=%s", run_id)

            ctx = await self._runner.run(
                run_id=run_id,
                input=IngestInput(source_path=tmp_path),
                initial_data=IngestData(),
            )

            document_id = ctx.data.document_id
            if document_id is None:
                raise IngestFailedError("Saga completed but document_id is None")

            doc = await self._knowledge_store.get_document_metadata(document_id)
            if doc is None:
                raise IngestFailedError(
                    f"Document {document_id!r} not found in store after ingest"
                )

            logger.info(
                "Ingest completed document_id=%s category=%s",
                document_id,
                doc.category,
            )
            return doc

        except IngestFailedError:
            raise
        except Exception as e:
            logger.error("Ingest pipeline failed: %s", e, exc_info=True)
            raise IngestFailedError(f"Ingest pipeline failed: {e}") from e
        finally:
            if tmp_path is not None and os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                    logger.debug("Deleted temp file: %s", tmp_path)
                except OSError:
                    logger.warning("Failed to delete temp file: %s", tmp_path)

    async def list_documents(self) -> list[DocumentMetadata]:
        """Return all indexed documents ordered by date descending.

        Returns:
            List of DocumentMetadata objects.
        """
        return await self._knowledge_store.list_documents_by_date(limit=500)
