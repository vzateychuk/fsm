import hashlib
from dataclasses import dataclass
from typing import ClassVar

from fsm.core import RunContext
from pipelines.ingest.guards import assert_raw_content
from pipelines.ingest.models import IngestInput, IngestData


@dataclass(slots=True)
class PreprocessText:
    """S2: Normalize text and compute SHA256 hash"""

    id: ClassVar[str] = "preprocess_text"
    desc: ClassVar[str] = "Normalize text and compute SHA256 hash"

    async def run(self, ctx: RunContext[IngestInput, IngestData]) -> None:
        ctx.data.desc = self.desc
        # Remove BOM, normalize line breaks
        content = assert_raw_content(ctx.data, self.id)
        content = content.lstrip("﻿")
        content = content.replace("\r\n", "\n")
        ctx.data.raw_content = content
        # Compute SHA256
        ctx.data.file_hash = hashlib.sha256(content.encode()).hexdigest()
        ctx.data.desc = f"Preprocessed, hash={ctx.data.file_hash[:16]}..."
