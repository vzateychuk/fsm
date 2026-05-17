from dataclasses import dataclass
from typing import ClassVar

from fsm.core import RunContext
from pipelines.ingest.guards import assert_file_hash, assert_raw_content
from pipelines.ingest.models import IngestData, IngestInput
from store.filestore import FileStore


@dataclass(slots=True)
class PersistSourceFile:
    """S7.5: Save source document to file storage"""

    id: ClassVar[str] = "persist_source_file"
    desc: ClassVar[str] = "Save source document to file storage"
    store: FileStore

    async def run(self, ctx: RunContext[IngestInput, IngestData]) -> None:
        ctx.data.desc = self.desc
        file_hash = assert_file_hash(ctx.data, self.id)
        raw_content = assert_raw_content(ctx.data, self.id)
        document_id = file_hash[:32]

        await self.store.save_source(
            document_id=document_id,
            source_path=ctx.input.source_path,
            content=raw_content,
        )

        ctx.data.desc = f"Source file saved: {document_id}"
