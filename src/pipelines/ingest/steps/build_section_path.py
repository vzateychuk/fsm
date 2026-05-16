from dataclasses import dataclass
from typing import ClassVar

from fsm.core import RunContext
from pipelines.ingest.guards import assert_tokens
from pipelines.ingest.models import BlockEvent, IngestData, IngestInput


@dataclass(slots=True)
class BuildSectionPath:
    """S5: Build hierarchical section paths for each block.

    Maintains a stack of heading contexts and computes section_path for each token
    (e.g., "H1 > H2" for content under H1 and H2 headings).
    Outputs block_events: list[BlockEvent] with token + section_path + heading context.
    """

    id: ClassVar[str] = "build_section_path"
    desc: ClassVar[str] = "Compute hierarchical breadcrumb context for each block"

    async def run(self, ctx: RunContext[IngestInput, IngestData]) -> None:
        ctx.data.desc = self.desc
        tokens = assert_tokens(ctx.data, self.id)

        section_stack: list[tuple[int, str]] = []
        block_events: list[BlockEvent] = []

        for token in tokens:
            if token.type == "heading":
                level = token.level
                heading_text = token.content.lstrip("#").strip()

                while section_stack and section_stack[-1][0] >= level:
                    section_stack.pop()
                section_stack.append((level, heading_text))
            else:
                section_path = " > ".join([text for _, text in section_stack])
                heading = section_stack[-1][1] if section_stack else None

                event: BlockEvent = {
                    "token": token,
                    "section_path": section_path,
                    "heading": heading,
                }
                block_events.append(event)

        ctx.data.block_events = block_events
        ctx.data.desc = f"Computed breadcrumb context for {len(block_events)} blocks"
