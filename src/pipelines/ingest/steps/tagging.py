from dataclasses import dataclass
from typing import Any, ClassVar

from fsm.core import RunContext
from pipelines.ingest.guards import assert_chunks
from pipelines.ingest.models import IngestData, IngestInput


@dataclass(slots=True)
class Tagging:
    """S8: Tag chunks deterministically"""

    id: ClassVar[str] = "tagging"
    desc: ClassVar[str] = "Extract meaningful terms for FTS boosting"

    async def run(self, ctx: RunContext[IngestInput, IngestData]) -> None:
        ctx.data.desc = self.desc
        chunks = assert_chunks(ctx.data, self.id)
        tagged_chunks: list[dict[str, Any]] = []

        for chunk in chunks:
            # Simple tagging: first words from heading (skip numbers and short words)
            heading = chunk["heading"]
            tags = []
            for word in heading.split():
                # Skip numbers and short words
                if word and not word[0].isdigit() and len(word) > 2:
                    tags.append(word.lower())

            tagged_chunks.append({
                **chunk,
                "tags": tags[:5],
                "tags_text": " ".join(tags[:5])
            })

        ctx.data.tagged_chunks = tagged_chunks  # type: ignore[assignment]
        ctx.data.desc = f"Tagged {len(tagged_chunks)} chunks"
