from dataclasses import dataclass

from fsm.core import RunContext
from pipelines.ingest.models import IngestInput, IngestData


@dataclass(slots=True)
class ChunkifyBlocks:
    """S6: Group tokens into logical chunks with hierarchical section path"""

    id = "chunkify_blocks"
    desc = "Convert markdown blocks into atomic chunks with breadcrumb context for RAG"

    async def run(self, ctx: RunContext[IngestInput, IngestData]) -> None:
        ctx.data.desc = "Chunkifying blocks with section paths"
        chunks = []
        current_chunk = {"heading": "", "section_path": "", "content": [], "tokens": []}
        section_path = []

        for token in ctx.data.tokens:
            if token["type"] == "heading":
                level = token["level"]
                # Trim path to correct depth
                section_path = section_path[:level - 1]
                section_path.append(token["content"].lstrip("#").strip())

                if level <= 2:
                    # Major heading — start new chunk
                    if current_chunk["content"]:
                        chunks.append(current_chunk)
                    current_chunk = {
                        "heading": token["content"].lstrip("#").strip(),
                        "section_path": " > ".join(section_path),
                        "content": [],
                        "tokens": [token]
                    }
            else:
                current_chunk["content"].append(token["content"])
                current_chunk["tokens"].append(token)

        if current_chunk["content"]:
            chunks.append(current_chunk)

        ctx.data.chunks = chunks
        ctx.data.desc = f"Created {len(chunks)} chunks with breadcrumbs"
