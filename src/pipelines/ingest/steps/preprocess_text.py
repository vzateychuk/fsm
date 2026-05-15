import hashlib
from dataclasses import dataclass
from typing import ClassVar

from fsm.core import RunContext
from pipelines.ingest.guards import assert_raw_content
from pipelines.ingest.models import IngestData, IngestInput


@dataclass(slots=True)
class PreprocessText:
    """S2: Normalize text and compute SHA256 hash

    Normalization (Phase 1 minimum):
    - Remove BOM
    - Normalize line breaks (\r\n and \r to \n)
    - Strip binary noise (\x00, control chars except \n/\t)
    - Replace NBSP ( ) with space
    - Compute deterministic SHA256 (utf-8 encoded)
    """

    id: ClassVar[str] = "preprocess_text"
    desc: ClassVar[str] = "Normalize text and compute SHA256 hash"

    async def run(self, ctx: RunContext[IngestInput, IngestData]) -> None:
        ctx.data.desc = self.desc
        content = assert_raw_content(ctx.data, self.id)

        # 1. Remove BOM
        content = content.lstrip("﻿")

        # 2. Normalize line breaks: \r\n and \r to \n
        content = content.replace("\r\n", "\n")
        content = content.replace("\r", "\n")

        # 3. Strip binary noise: remove \x00 and control chars (except \n, \t)
        content = "".join(
            ch for ch in content
            if ch in ("\n", "\t") or ord(ch) >= 0x20 or ch in ("​", "‌", "‍")
        )

        # 4. Replace NBSP ( ) with regular space
        content = content.replace(" ", " ")

        ctx.data.raw_content = content

        # 5. Compute SHA256 from normalized text (explicit utf-8)
        ctx.data.file_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        ctx.data.desc = f"Preprocessed, hash={ctx.data.file_hash[:16]}..."
