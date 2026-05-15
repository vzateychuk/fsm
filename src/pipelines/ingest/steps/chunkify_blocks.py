from dataclasses import dataclass
from typing import Any, ClassVar

from fsm.core import RunContext
from pipelines.ingest.guards import assert_tokens
from pipelines.ingest.models import IngestData, IngestInput


@dataclass(slots=True)
class ChunkifyBlocks:
    """S6: Group tokens into logical chunks with hierarchical section path"""

    id: ClassVar[str] = "chunkify_blocks"
    desc: ClassVar[str] = "Convert markdown blocks into atomic chunks with breadcrumb context for RAG"

    async def run(self, ctx: RunContext[IngestInput, IngestData]) -> None:
        ctx.data.desc = self.desc
        tokens = assert_tokens(ctx.data, self.id)
        chunks: list[dict[str, Any]] = []
        current_chunk: dict[str, Any] = {"heading": "", "section_path": "", "content": [], "tokens": []}
        section_path: list[str] = []

        for token in tokens:
            if token.type == "heading":
                level = token.level
                # Trim path to correct depth
                section_path = section_path[:level - 1]
                section_path.append(token.content.lstrip("#").strip())

                if level <= 2:
                    # Major heading — start new chunk
                    if current_chunk["content"]:
                        chunks.append(current_chunk)
                    current_chunk = {
                        "heading": token.content.lstrip("#").strip(),
                        "section_path": " > ".join(section_path),
                        "content": [],
                        "tokens": [token]
                    }
            else:
                current_chunk["content"].append(token.content)
                current_chunk["tokens"].append(token)

        if current_chunk["content"]:
            chunks.append(current_chunk)

        ctx.data.chunks = chunks  # type: ignore[assignment]
        ctx.data.desc = f"Created {len(chunks)} chunks with breadcrumbs"
