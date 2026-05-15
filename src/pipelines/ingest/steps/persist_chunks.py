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
        # Simulation: generate IDs for chunks
        if not ctx.data.document_id:
            raise RuntimeError("Field 'document_id' is None. This step requires it to be filled by 'PersistDocument' first.")
        if not ctx.data.tagged_chunks:
            raise RuntimeError("Field 'tagged_chunks' is None. This step requires it to be filled by 'Tagging' first.")
        ctx.data.chunk_ids = [f"{ctx.data.document_id}_{i}" for i in range(len(ctx.data.tagged_chunks))]
        ctx.data.desc = f"Persisted {len(ctx.data.chunk_ids)} chunks"
