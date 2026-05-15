from dataclasses import dataclass
from typing import ClassVar

from common.utils.parsers import find_schema_id
from fsm.core import RunContext
from pipelines.ingest.guards import assert_raw_content
from pipelines.ingest.models import IngestData, IngestInput


@dataclass(slots=True)
class SplitControlBlocks:
    """S4: Split document into markdown body and footer metadata.

    Footer-only approach: extracts metadata block from end of document (starting with "metadata:").
    No frontmatter processing (--- at start is treated as markdown HR, not YAML).
    Removes Target Schema ID line from body to avoid markdown parsing pollution.
    """

    id: ClassVar[str] = "split_control_blocks"
    desc: ClassVar[str] = "Split into markdown body and footer metadata"

    async def run(self, ctx: RunContext[IngestInput, IngestData]) -> None:
        ctx.data.desc = self.desc
        content = assert_raw_content(ctx.data, self.id)
        lines = content.split("\n")

        # Step 1: Extract footer metadata (reverse scan for "metadata:" marker at line start)
        meta_idx = None
        for i in range(len(lines) - 1, -1, -1):
            stripped = lines[i].strip().lower()
            if stripped == "metadata:" or stripped.startswith("metadata:"):
                meta_idx = i
                break

        if meta_idx is not None:
            # Found footer metadata block
            md_body_lines = lines[:meta_idx]
            # Remove optional --- separator immediately before metadata (footer delimiter)
            if md_body_lines and md_body_lines[-1].strip() == "---":
                md_body_lines.pop()
            ctx.data.metadata_block = "\n".join(lines[meta_idx:])
        else:
            md_body_lines = lines
            ctx.data.metadata_block = None

        # Step 2: Remove Target Schema ID line from body (search first ~30 lines)
        # This prevents schema marker from polluting markdown parsing/chunking
        match = find_schema_id(md_body_lines, search_limit=30)
        if match:
            md_body_lines.pop(match.line_number)

        ctx.data.md_body = "\n".join(md_body_lines)
        ctx.data.desc = f"Split: metadata={bool(ctx.data.metadata_block)}, body_lines={len(ctx.data.md_body.split(chr(10)))}"
