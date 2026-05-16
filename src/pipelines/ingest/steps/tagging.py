from dataclasses import dataclass
from typing import ClassVar

from fsm.core import RunContext
from pipelines.ingest.guards import assert_chunks
from pipelines.ingest.models import ChunkTagged, IngestData, IngestInput

# Stub — populate in Phase 5
_ALIAS_MAP: dict[str, list[str]] = {}

_STOPWORDS = {"для", "при", "или", "что", "это", "как", "его", "ее", "её", "the", "and", "for", "with"}


@dataclass(slots=True)
class Tagging:
    """S7: Tag chunks deterministically from section_path + heading."""

    id: ClassVar[str] = "tagging"
    desc: ClassVar[str] = "Extract meaningful terms for FTS boosting"

    async def run(self, ctx: RunContext[IngestInput, IngestData]) -> None:
        ctx.data.desc = self.desc
        chunks = assert_chunks(ctx.data, self.id)
        tagged_chunks: list[ChunkTagged] = []

        for chunk in chunks:
            words: set[str] = set()
            for part in (chunk.get("section_path") or "").split(" > "):
                words.update(w.lower() for w in part.split() if w)
            for w in (chunk.get("heading") or "").split():
                words.add(w.lower())

            filtered = sorted(
                w for w in words
                if len(w) > 2
                and not any(c.isdigit() for c in w)
                and w not in _STOPWORDS
            )

            expanded: list[str] = []
            seen: set[str] = set()
            for w in filtered:
                if w not in seen:
                    expanded.append(w)
                    seen.add(w)
                for alias in _ALIAS_MAP.get(w, []):
                    if alias not in seen:
                        expanded.append(alias)
                        seen.add(alias)

            tagged_chunks.append({**chunk, "tags_text": " ".join(expanded[:10])})

        ctx.data.tagged_chunks = tagged_chunks
        ctx.data.desc = f"Tagged {len(tagged_chunks)} chunks"
