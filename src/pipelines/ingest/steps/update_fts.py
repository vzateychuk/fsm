from dataclasses import dataclass
from typing import ClassVar

from fsm.core import RunContext
from pipelines.ingest.models import IngestData, IngestInput


@dataclass(slots=True)
class UpdateFTS:
    """S11: Update FTS5 index with chunks"""

    id: ClassVar[str] = "update_fts"
    desc: ClassVar[str] = "Update FTS5 search index"

    async def run(self, ctx: RunContext[IngestInput, IngestData]) -> None:
        ctx.data.desc = self.desc
        # Simulation: mark FTS as updated
        if not ctx.data.chunk_ids:
            raise RuntimeError("Field 'chunk_ids' is None. This step requires it to be filled by 'PersistChunks' first.")
        ctx.data.fts_updated = True
        ctx.data.desc = f"FTS5 index updated with {len(ctx.data.chunk_ids)} entries"
