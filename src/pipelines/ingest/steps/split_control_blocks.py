from dataclasses import dataclass
from typing import ClassVar

from fsm.core import RunContext
from pipelines.ingest.guards import assert_raw_content
from pipelines.ingest.models import IngestInput, IngestData


@dataclass(slots=True)
class SplitControlBlocks:
    """S4: Split into schema line, metadata block, and markdown body"""

    id: ClassVar[str] = "split_control_blocks"
    desc: ClassVar[str] = "Split document into control blocks (schema, metadata, body)"

    async def run(self, ctx: RunContext[IngestInput, IngestData]) -> None:
        ctx.data.desc = self.desc
        content = assert_raw_content(ctx.data, self.id)
        lines = content.split("\n")
        idx = 0

        # Metadata block (between --- markers)
        metadata_lines = []
        if idx < len(lines) and lines[idx].strip() == "---":
            idx += 1
            while idx < len(lines) and lines[idx].strip() != "---":
                metadata_lines.append(lines[idx])
                idx += 1
            if idx < len(lines) and lines[idx].strip() == "---":
                idx += 1
            ctx.data.metadata_block = "\n".join(metadata_lines)

        # Markdown body (rest)
        ctx.data.md_body = "\n".join(lines[idx:])
        ctx.data.desc = f"Split: metadata={bool(ctx.data.metadata_block)}, body_lines={len(ctx.data.md_body.split(chr(10)))}"
