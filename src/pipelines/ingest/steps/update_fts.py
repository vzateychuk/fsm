from dataclasses import dataclass

from fsm.core import RunContext
from pipelines.ingest.models import IngestInput, IngestData


@dataclass(slots=True)
class UpdateFTS:
    """S11: Update FTS5 index with chunks"""

    id = "update_fts"
    desc = "Update FTS5 search index"

    async def run(self, ctx: RunContext[IngestInput, IngestData]) -> None:
        ctx.data.desc = self.desc
        # Simulation: mark FTS as updated
        ctx.data.fts_updated = True
        ctx.data.desc = f"FTS5 index updated with {len(ctx.data.chunk_ids)} entries"
