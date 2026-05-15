from dataclasses import dataclass
from typing import ClassVar

from common.utils.parsers import find_schema_id
from fsm.core import RunContext
from pipelines.ingest.guards import assert_raw_content
from pipelines.ingest.models import IngestData, IngestInput


@dataclass(slots=True)
class SplitControlBlocks:
    """S4: Split into schema line, metadata block, and markdown body"""

    id: ClassVar[str] = "split_control_blocks"
    desc: ClassVar[str] = "Split document into control blocks (schema, metadata, body)"

    async def run(self, ctx: RunContext[IngestInput, IngestData]) -> None:
        ctx.data.desc = self.desc
        content = assert_raw_content(ctx.data, self.id)
        lines = content.split("\n")

        # Step 1: Extract footer metadata (reverse scan for "metadata:" marker)
        meta_idx = None
        for i in range(len(lines) - 1, -1, -1):
            if lines[i].strip().lower().startswith("metadata:"):
                meta_idx = i
                break

        if meta_idx is not None:
            # Remove optional --- separator before metadata block
            if meta_idx > 0 and lines[meta_idx - 1].strip() == "---":
                md_body_lines = lines[:meta_idx - 1]
            else:
                md_body_lines = lines[:meta_idx]
            ctx.data.metadata_block = "\n".join(lines[meta_idx:])
        else:
            md_body_lines = lines
            ctx.data.metadata_block = None

        # Step 2: Remove Target Schema ID line from body (first ~30 lines)
        match = find_schema_id(md_body_lines, search_limit=30)
        if match:
            md_body_lines.pop(match.line_number)

        ctx.data.md_body = "\n".join(md_body_lines)
        ctx.data.desc = f"Split: metadata={bool(ctx.data.metadata_block)}, body_lines={len(ctx.data.md_body.split(chr(10)))}"
