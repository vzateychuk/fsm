"""Knowledge base context bundle builder."""

from datetime import date, timedelta

from src.pipelines.consult.config import ConsultConfig
from src.pipelines.consult.models import KBContextBundle
from src.store.knowledge_store import ChunkSearchResult


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
    8. Build provenance (doc_id | source | section_path)
    """

    def __init__(self, config: ConsultConfig) -> None:
        self.config = config

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
            KBContextBundle with top_chunks, kb_excerpts, provenance.
        """
        merged = self._deduplicate(query_chunks, recency_chunks)
        merged = merged[: self.config.bundle.max_total_chunks]

        formatted = self._format_by_category(merged)
        formatted = self._truncate_to_char_limit(formatted)

        top_chunks_list = formatted[: self.config.excerpts.top_chunks_count]
        kb_excerpts_list = formatted[self.config.excerpts.top_chunks_count :]

        top_chunks_text = [
            self._truncate_text_lines(chunk.text, self.config.excerpts.top_chunks_lines)
            for chunk in top_chunks_list
        ]

        kb_excerpts_text = [chunk.text for chunk in kb_excerpts_list]

        provenance = self._build_provenance(kb_excerpts_list)

        return KBContextBundle(
            top_chunks=top_chunks_text,
            kb_excerpts=kb_excerpts_text,
            provenance=provenance,
        )

    @staticmethod
    def _deduplicate(
        query_chunks: list[ChunkSearchResult],
        recency_chunks: list[ChunkSearchResult],
    ) -> list[ChunkSearchResult]:
        """Deduplicate by chunk_id, preserving query priority.

        Query chunks appear first in the result, then new recency chunks.
        """
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
        """Truncate text by category rules.

        Returns new ChunkSearchResult objects with truncated text.
        """
        formatted: list[ChunkSearchResult] = []
        for chunk in chunks:
            max_lines = self._get_max_lines_for_category(chunk.category)
            truncated_text = self._truncate_text_lines(chunk.text, max_lines)
            formatted.append(
                ChunkSearchResult(
                    chunk_id=chunk.chunk_id,
                    document_id=chunk.document_id,
                    chunk_no=chunk.chunk_no,
                    kind=chunk.kind,
                    text=truncated_text,
                    section_path=chunk.section_path,
                    heading=chunk.heading,
                    tags_text=chunk.tags_text,
                    source_path=chunk.source_path,
                    category=chunk.category,
                    rank=chunk.rank,
                )
            )
        return formatted

    def _get_max_lines_for_category(self, category: str) -> int:
        """Get max lines allowed for a category.

        - full_text_categories: return very large number (no truncation)
        - category_line_limits: return configured limit
        - default: return max_lines_default
        """
        if category in self.config.excerpts.full_text_categories:
            return 999_999
        if category in self.config.excerpts.category_line_limits:
            return self.config.excerpts.category_line_limits[category]
        return self.config.excerpts.max_lines_default

    @staticmethod
    def _truncate_text_lines(text: str, max_lines: int) -> str:
        """Truncate text to max_lines (counted from start)."""
        lines = text.split("\n")
        if len(lines) <= max_lines:
            return text
        return "\n".join(lines[:max_lines])

    def _truncate_to_char_limit(
        self,
        chunks: list[ChunkSearchResult],
    ) -> list[ChunkSearchResult]:
        """Drop chunks from tail until total chars <= max_total_chars.

        This is applied AFTER line truncation, to respect character budget.
        """
        total_chars = sum(len(chunk.text) for chunk in chunks)
        if total_chars <= self.config.bundle.max_total_chars:
            return chunks

        result = chunks.copy()
        while result and sum(len(c.text) for c in result) > self.config.bundle.max_total_chars:
            result.pop()

        return result

    @staticmethod
    def _build_provenance(chunks: list[ChunkSearchResult]) -> list[str]:
        """Build provenance entries (doc_id | source_path | section_path)."""
        provenance: list[str] = []
        for chunk in chunks:
            section = chunk.section_path or "(no section)"
            entry = f"{chunk.document_id} | {chunk.source_path} | {section}"
            provenance.append(entry)
        return provenance
