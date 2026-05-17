from dataclasses import dataclass
from datetime import datetime, timezone
from typing import ClassVar, cast

from fsm.core import RunContext
from pipelines.ingest.guards import assert_file_hash
from pipelines.ingest.models import IngestData, IngestInput
from store.knowledge_store import DocType, KnowledgeStore


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
        filestore_path = ctx.data.filestore_path or ctx.input.source_path
        await self.store.save_document(
            document_id=document_id,
            source_path=filestore_path,
            source_sha256=file_hash,
            doc_type=cast(DocType, ctx.data.target_schema),
            indexed_at=datetime.now(timezone.utc).isoformat(),
            raw_text=ctx.data.raw_content or "",
        )
        ctx.data.document_id = document_id
        ctx.data.desc = f"Document saved: {document_id}"
