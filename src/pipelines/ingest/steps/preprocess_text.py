import hashlib
from dataclasses import dataclass

from fsm.core import RunContext
from pipelines.ingest.models import IngestInput, IngestData


@dataclass(slots=True)
class PreprocessText:
    """S2: Normalize text and compute SHA256 hash"""

    id = "preprocess_text"
    desc = "Normalize text and compute SHA256 hash"

    async def run(self, ctx: RunContext[IngestInput, IngestData]) -> None:
        ctx.data.desc = "Preprocessing text and computing hash"
        # Remove BOM, normalize line breaks
        content = ctx.data.raw_content.lstrip("﻿")
        content = content.replace("\r\n", "\n")
        ctx.data.raw_content = content
        # Compute SHA256
        ctx.data.file_hash = hashlib.sha256(content.encode()).hexdigest()
        ctx.data.desc = f"Preprocessed, hash={ctx.data.file_hash[:16]}..."
