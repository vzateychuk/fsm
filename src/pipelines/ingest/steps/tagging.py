from dataclasses import dataclass
from typing import ClassVar

from fsm.core import RunContext
from pipelines.ingest.alias_map import ALIAS_MAP, is_stopword, is_unit
from pipelines.ingest.guards import assert_chunks
from pipelines.ingest.models import ChunkTagged, IngestData, IngestInput
from pipelines.ingest.tokenizer import tokenize


def _keep(token: str) -> bool:
    """Check if token passes all filters: length, digits, units, stopwords, internal punct."""
    from pipelines.ingest.tokenizer import _INVALID_CHARS

    return (
        len(token) >= 3
        and not any(c.isdigit() for c in token)
        and not is_unit(token)
        and not is_stopword(token)
        and not any(c in _INVALID_CHARS for c in token)
    )


def _build_tags(sources: list[str]) -> str:
    filtered: list[str] = []
    for source in sources:
        for raw in tokenize(source):
            if _keep(raw):
                filtered.append(raw)

    accumulated: list[str] = []
    for token in filtered:
        if "-" in token:
            parts = [p for p in token.split("-") if p]
            for p in parts + ["".join(parts)]:
                if _keep(p):
                    accumulated.append(p)
        elif "/" in token:
            parts = [p for p in token.split("/") if p]
            for p in parts:
                if _keep(p):
                    accumulated.append(p)
        else:
            accumulated.append(token)

    alias_extras: list[str] = []
    for token in accumulated:
        for alias in ALIAS_MAP.get(token, []):
            if _keep(alias):
                alias_extras.append(alias)

    return " ".join(sorted(set(accumulated + alias_extras)))


@dataclass(slots=True)
class Tagging:
    """S7: Build deterministic tags_text per chunk.

    Pipeline: tokenize sources → filter (digits/units/stopwords/len) →
    expand composites (hyphen/slash) → alias expansion → dedup+sort.
    Sources: target_schema (doc_type), kind, section_path, heading.
    """

    id: ClassVar[str] = "tagging"
    desc: ClassVar[str] = "Extract meaningful terms for FTS boosting"

    async def run(self, ctx: RunContext[IngestInput, IngestData]) -> None:
        ctx.data.desc = self.desc
        chunks = assert_chunks(ctx.data, self.id)
        doc_type = ctx.data.target_schema or ""
        tagged_chunks: list[ChunkTagged] = []

        for chunk in chunks:
            sources = [
                doc_type,
                chunk["kind"],
                chunk["section_path"],
                chunk["heading"] or "",
            ]
            tags_text = _build_tags(sources)
            tagged_chunks.append({**chunk, "tags_text": tags_text})

        ctx.data.tagged_chunks = tagged_chunks
        ctx.data.desc = f"Tagged {len(tagged_chunks)} chunks"
