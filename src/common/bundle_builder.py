"""Shared KB context bundle configuration, model, and builder."""

from __future__ import annotations

from dataclasses import dataclass, field

from pydantic import BaseModel

from src.store.knowledge_store import ChunkSearchResult


@dataclass
class BundleConfig:
    """Configuration for bundle assembly.

    Controls aggregation and size limits for the knowledge base context bundle.
    """

    max_total_chunks: int
    """Hard limit on total chunks in the final bundle (query + recency combined)."""
    max_total_chars: int
    """Hard limit on total characters in the final bundle.
    Applied AFTER line-truncation. Chunks are dropped from the tail until total fits.
    """


@dataclass
class ExcerptsConfig:
    """Configuration for excerpt formatting and truncation."""

    top_chunks_count: int
    """Number of highest-ranked chunks to promote to 'Top Chunks' section."""
    top_chunks_lines: int
    """Line limit for each chunk in the Top Chunks section."""
    max_lines_default: int
    """Default line limit for categories without explicit limits."""
    max_chunk_chars: int = 0
    """Maximum characters per chunk. 0 means no limit. Applied after line truncation."""
    category_line_limits: dict[str, int] = field(default_factory=dict)
    """Per-category line limits. Categories not listed fall back to max_lines_default."""


class KBContextBundle(BaseModel):
    """Formatted knowledge base context for the medical LLM."""

    top_chunks: list[str] = []
    kb_excerpts: list[str] = []
    provenance: list[str] = []


class KBContextBundleBuilder:
    """Builds formatted KB context bundle for the medical LLM.

    Implements 8-step algorithm:
    1. Accept query_chunks (BM25-ranked)
    2. Accept recency_chunks (from recent documents)
    3. Deduplicate by chunk_id (query priority)
    4. Apply max_total_chunks limit
    5. Format text by category (truncate lines)
    6. Apply max_total_chars limit (from tail)
    7. Split into top_chunks (first N) and kb_excerpts (rest)
    8. Format with inline source attribution ([index] doc_id | chunk_N | section)
    """

    def __init__(self, bundle_config: BundleConfig, excerpts_config: ExcerptsConfig) -> None:
        self.bundle_config = bundle_config
        self.excerpts_config = excerpts_config

    def build(
        self,
        query_chunks: list[ChunkSearchResult],
        recency_chunks: list[ChunkSearchResult],
    ) -> KBContextBundle:
        """Build the context bundle.

        Args:
            query_chunks: BM25-ranked chunks from query retrieval.
            recency_chunks: Chunks from recent documents (rank=0.0).

        Returns:
            KBContextBundle with top_chunks and kb_excerpts (each prefixed with inline source).
            Provenance is included as source headers within each chunk text.
        """
        merged = self._deduplicate(query_chunks, recency_chunks)
        merged = merged[: self.bundle_config.max_total_chunks]

        formatted = self._format_by_category(merged)
        formatted = self._truncate_to_char_limit(formatted)

        top_chunks_list = formatted[: self.excerpts_config.top_chunks_count]
        kb_excerpts_list = formatted[self.excerpts_config.top_chunks_count :]

        top_chunks_text = []
        for i, chunk in enumerate(top_chunks_list, start=1):
            source_header = self._format_source_header(i, chunk)
            text = self._truncate_text_lines(chunk.text, self.excerpts_config.top_chunks_lines)
            top_chunks_text.append(f"{source_header}\n\n{text}")

        kb_excerpts_text = []
        for i, chunk in enumerate(kb_excerpts_list, start=len(top_chunks_list) + 1):
            source_header = self._format_source_header(i, chunk)
            kb_excerpts_text.append(f"{source_header}\n\n{chunk.text}")

        return KBContextBundle(
            top_chunks=top_chunks_text,
            kb_excerpts=kb_excerpts_text,
            provenance=[],  # Sources are inline in each chunk
        )

    @staticmethod
    def _deduplicate(
        query_chunks: list[ChunkSearchResult],
        recency_chunks: list[ChunkSearchResult],
    ) -> list[ChunkSearchResult]:
        """Deduplicate by chunk_id, preserving query priority."""
        seen: set[str] = set()
        result: list[ChunkSearchResult] = []

        for chunk in query_chunks:
            if chunk.chunk_id not in seen:
                seen.add(chunk.chunk_id)
                result.append(chunk)

        for chunk in recency_chunks:
            if chunk.chunk_id not in seen:
                seen.add(chunk.chunk_id)
                result.append(chunk)

        return result

    def _format_by_category(
        self,
        chunks: list[ChunkSearchResult],
    ) -> list[ChunkSearchResult]:
        """Truncate text by category rules, then optionally by char limit."""
        formatted: list[ChunkSearchResult] = []
        for chunk in chunks:
            max_lines = self._get_max_lines_for_category(chunk.category)
            text = self._truncate_text_lines(chunk.text, max_lines)
            if self.excerpts_config.max_chunk_chars > 0:
                text = self._truncate_text_chars(text, self.excerpts_config.max_chunk_chars)
            formatted.append(
                ChunkSearchResult(
                    chunk_id=chunk.chunk_id,
                    document_id=chunk.document_id,
                    chunk_no=chunk.chunk_no,
                    kind=chunk.kind,
                    text=text,
                    section_path=chunk.section_path,
                    heading=chunk.heading,
                    tags_text=chunk.tags_text,
                    source_path=chunk.source_path,
                    category=chunk.category,
                    document_date=chunk.document_date,
                    rank=chunk.rank,
                )
            )
        return formatted

    def _get_max_lines_for_category(self, category: str) -> int:
        if category in self.excerpts_config.category_line_limits:
            return self.excerpts_config.category_line_limits[category]
        return self.excerpts_config.max_lines_default

    @staticmethod
    def _truncate_text_lines(text: str, max_lines: int) -> str:
        lines = text.split("\n")
        if len(lines) <= max_lines:
            return text
        return "\n".join(lines[:max_lines])

    @staticmethod
    def _truncate_text_chars(text: str, max_chars: int) -> str:
        if len(text) <= max_chars:
            return text
        cut = text[:max_chars]
        last_newline = cut.rfind("\n")
        if last_newline > 0:
            return cut[:last_newline]
        return cut

    def _truncate_to_char_limit(
        self,
        chunks: list[ChunkSearchResult],
    ) -> list[ChunkSearchResult]:
        """Drop chunks from tail until total chars <= max_total_chars."""
        total_chars = sum(len(chunk.text) for chunk in chunks)
        if total_chars <= self.bundle_config.max_total_chars:
            return chunks

        result = chunks.copy()
        while result and sum(len(c.text) for c in result) > self.bundle_config.max_total_chars:
            result.pop()

        return result

    @staticmethod
    def _format_source_header(index: int, chunk: ChunkSearchResult) -> str:
        """Format: [index] source_path | document_date | category | section_path"""
        section = chunk.section_path or "(no section)"
        return f"[{index}] {chunk.source_path} | {chunk.document_date} | {chunk.category} | {section}"
