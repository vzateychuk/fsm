from dataclasses import dataclass

from fsm.core import RunContext
from pipelines.ingest.models import IngestInput, IngestData


@dataclass(slots=True)
class PersistDocument:
    """S9: Save document metadata to database"""

    id = "persist_document"
    desc = "Save document metadata to database"

    async def run(self, ctx: RunContext[IngestInput, IngestData]) -> None:
        ctx.data.desc = self.desc
        # Simulation: generate ID based on hash
        ctx.data.document_id = ctx.data.file_hash[:16]
        ctx.data.desc = f"Document persisted with ID: {ctx.data.document_id}"
