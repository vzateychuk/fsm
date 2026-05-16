from dataclasses import dataclass
from typing import ClassVar

from fsm.core import RunContext
from pipelines.ingest.models import IngestData, IngestInput


@dataclass(slots=True)
class PersistChunks:
    """S10: Save all chunks to database"""

    id: ClassVar[str] = "persist_chunks"
    desc: ClassVar[str] = "Save all chunks to database"

    async def run(self, ctx: RunContext[IngestInput, IngestData]) -> None:
        ctx.data.desc = self.desc
        if not ctx.data.document_id:
            raise RuntimeError("Field 'document_id' is None. This step requires it to be filled by 'PersistDocument' first.")
        if not ctx.data.tagged_chunks:
            raise RuntimeError("Field 'tagged_chunks' is None. This step requires it to be filled by 'Tagging' first.")
        chunk_ids: list[str] = []
        for i, chunk in enumerate(ctx.data.tagged_chunks):
            chunk["chunk_no"] = i
            chunk_ids.append(f"{ctx.data.document_id}_{i}")
        ctx.data.chunk_ids = chunk_ids
        ctx.data.desc = f"Persisted {len(chunk_ids)} chunks"
