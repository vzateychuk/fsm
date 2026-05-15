from dataclasses import dataclass

from fsm.core import RunContext
from pipelines.ingest.models import IngestInput, IngestData


@dataclass(slots=True)
class PersistChunks:
    """S10: Save all chunks to database"""

    id = "persist_chunks"
    desc = "Save all chunks to database"

    async def run(self, ctx: RunContext[IngestInput, IngestData]) -> None:
        ctx.data.desc = self.desc
        # Simulation: generate IDs for chunks
        ctx.data.chunk_ids = [f"{ctx.data.document_id}_{i}" for i in range(len(ctx.data.tagged_chunks))]
        ctx.data.desc = f"Persisted {len(ctx.data.chunk_ids)} chunks"
