from dataclasses import dataclass

from fsm.core import RunContext
from pipelines.ingest.models import IngestInput, IngestData


@dataclass(slots=True)
class Tagging:
    """S8: Tag chunks deterministically"""

    id = "tagging"
    desc = "Extract meaningful terms for FTS boosting"

    async def run(self, ctx: RunContext[IngestInput, IngestData]) -> None:
        ctx.data.desc = "Tagging chunks"
        tagged_chunks = []

        for chunk in ctx.data.chunks:
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

        ctx.data.tagged_chunks = tagged_chunks
        ctx.data.desc = f"Tagged {len(tagged_chunks)} chunks"
