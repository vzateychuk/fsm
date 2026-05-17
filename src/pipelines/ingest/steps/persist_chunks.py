from dataclasses import dataclass
from typing import ClassVar

from fsm.core import RunContext
from pipelines.ingest.guards import assert_document_id
from pipelines.ingest.models import IngestData, IngestInput
from store.knowledge_store import KnowledgeStore


@dataclass(slots=True)
class PersistChunks:
    """S9: Replace chunks and sync FTS in knowledge base (atomic)"""

    id: ClassVar[str] = "persist_chunks"
    desc: ClassVar[str] = "Replace chunks and sync FTS in knowledge base"
    store: KnowledgeStore

    async def run(self, ctx: RunContext[IngestInput, IngestData]) -> None:
        ctx.data.desc = self.desc
        document_id = assert_document_id(ctx.data, self.id)
        ctx.data.chunk_ids = await self.store.replace_document_chunks(
            document_id=document_id,
            chunks=ctx.data.tagged_chunks,
        )
        ctx.data.fts_updated = True
        ctx.data.desc = f"Persisted {len(ctx.data.chunk_ids)} chunks with FTS sync"
