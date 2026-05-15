from dataclasses import dataclass
from typing import ClassVar

from fsm.core import RunContext
from pipelines.ingest.guards import assert_file_hash
from pipelines.ingest.models import IngestData, IngestInput


@dataclass(slots=True)
class PersistDocument:
    """S9: Save document metadata to database"""

    id: ClassVar[str] = "persist_document"
    desc: ClassVar[str] = "Save document metadata to database"

    async def run(self, ctx: RunContext[IngestInput, IngestData]) -> None:
        ctx.data.desc = self.desc
        # Simulation: generate ID based on hash
        file_hash = assert_file_hash(ctx.data, self.id)
        ctx.data.document_id = file_hash[:16]
        ctx.data.desc = f"Document persisted with ID: {ctx.data.document_id}"
