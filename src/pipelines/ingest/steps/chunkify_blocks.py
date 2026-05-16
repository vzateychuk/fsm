from dataclasses import dataclass
from typing import ClassVar

from fsm.core import RunContext
from pipelines.ingest.guards import assert_block_events
from pipelines.ingest.models import (
    ChunkBase,
    ChunkKind,
    IngestData,
    IngestError,
    IngestInput,
    MdToken,
)


def _classify_kind(token: MdToken) -> ChunkKind:
    if token.type == "table":
        return "table"
    if token.type == "list":
        return "list"
    if token.type == "paragraph" and token.subtype == "fact":
        return "fact"
    return "section"


def _split_text(text: str, max_chars: int) -> list[str]:
    """Split at double-newline boundaries if text exceeds max_chars.

    Note: markdown-it paragraph tokens rarely contain '\\n\\n' since softbreaks
    become spaces. This split is a safeguard for edge cases (fence content, etc.).
    A single paragraph > max_chars with no '\\n\\n' is kept whole — no silent hard-cut.
    """
    if len(text) <= max_chars:
        return [text]
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if len(paragraphs) <= 1:
        return [text]

    result: list[str] = []
    current: list[str] = []
    current_len = 0
    for para in paragraphs:
        if current and current_len + len(para) > max_chars:
            result.append("\n\n".join(current))
            current = [para]
            current_len = len(para)
        else:
            current.append(para)
            current_len += len(para)
    if current:
        result.append("\n\n".join(current))
    return result


@dataclass(slots=True)
class ChunkifyBlocks:
    """S6: Classify block events by kind and produce chunks.

    1:1 for table/list/fact; section chunks split at paragraph boundaries
    if content exceeds max_section_chars. chunk_no is NOT assigned here — S9 does it.
    """

    id: ClassVar[str] = "chunkify_blocks"
    desc: ClassVar[str] = "Convert markdown blocks into typed chunks with breadcrumb context"

    max_section_chars: int = 4000

    async def run(self, ctx: RunContext[IngestInput, IngestData]) -> None:
        ctx.data.desc = self.desc
        block_events = assert_block_events(ctx.data, self.id)
        chunks: list[ChunkBase] = []

        for event in block_events:
            token = event["token"]
            kind = _classify_kind(token)

            if kind == "section" and len(token.content) > self.max_section_chars:
                parts = _split_text(token.content, self.max_section_chars)
            else:
                parts = [token.content]

            for part in parts:
                if not part.strip():
                    continue
                chunks.append({
                    "kind": kind,
                    "text": part,
                    "section_path": event["section_path"],
                    "heading": event["heading"],
                })

        if not chunks:
            raise IngestError("E_EMPTY_CHUNKS", "No chunks produced from document body")

        ctx.data.chunks = chunks
        ctx.data.desc = f"Created {len(chunks)} chunks"
