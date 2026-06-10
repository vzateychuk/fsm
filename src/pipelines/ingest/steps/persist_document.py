from dataclasses import dataclass
from datetime import UTC, datetime
import logging
from typing import ClassVar

from fsm.core import RunContext
from pipelines.ingest.guards import assert_file_hash
from pipelines.ingest.models import IngestData, IngestInput
from store.knowledge_store import KnowledgeStore

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class PersistDocument:
    """S8: Save document metadata to knowledge base"""

    id: ClassVar[str] = "persist_document"
    desc: ClassVar[str] = "Save document metadata to knowledge base"
    store: KnowledgeStore

    async def run(self, ctx: RunContext[IngestInput, IngestData]) -> None:
        ctx.data.desc = self.desc
        file_hash = assert_file_hash(ctx.data, self.id)
        document_id = file_hash[:32]
        await self.store.save_document(
            document_id=document_id,
            source_path=ctx.input.original_filename,
            source_sha256=file_hash,
            category=ctx.data.target_schema or "",
            indexed_at=datetime.now(UTC).isoformat(),
            document_date=ctx.data.document_date,
            raw_text=ctx.data.raw_content or "",
        )
        ctx.data.document_id = document_id
        ctx.data.desc = f"Document saved: {document_id}"
        logger.info(
            "Document saved: document_id=%s filename=%s",
            document_id,
            ctx.input.original_filename,
        )
