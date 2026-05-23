from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from common.types import ChunkKind

if TYPE_CHECKING:
    from pipelines.ingest.models import ChunkTagged

Category = str


@dataclass(frozen=True, slots=True)
class DocumentMetadata:
    document_id: str
    source_path: str
    category: Category
    document_date: str  # ISO format YYYY-MM-DD
    indexed_at: str


@dataclass(frozen=True, slots=True)
class ChunkSearchResult:
    chunk_id: str
    document_id: str
    chunk_no: int
    kind: ChunkKind
    text: str
    section_path: str | None
    heading: str | None
    tags_text: str | None
    source_path: str
    category: Category
    document_date: str  # ISO format YYYY-MM-DD
    rank: float  # bm25, lower is better


class KnowledgeStore(Protocol):
    async def save_document(
        self,
        *,
        document_id: str,
        source_path: str,
        source_sha256: str,
        category: Category,
        indexed_at: str,
        document_date: str,
        raw_text: str,
    ) -> None: ...

    async def replace_document_chunks(
        self,
        *,
        document_id: str,
        chunks: list[ChunkTagged],
    ) -> list[str]:
        """Replace chunks for document and sync FTS atomically. Returns deterministic chunk_ids."""
        ...

    async def search_chunks(
        self,
        query: str,
        *,
        category: Category | None = None,
        document_id: str | None = None,
        kinds: set[ChunkKind] | None = None,
        section_path_prefix: str | None = None,
        from_date: str | None = None,
        to_date: str | None = None,
        limit: int = 20,
        limit_per_document: int = 3,
        prelimit: int = 200,
        bm25_weights: tuple[float, float, float, float] | None = None,
        meta_score_factor: float = 0.1,
    ) -> list[ChunkSearchResult]: ...

    async def get_documents_raw_text(
        self,
        document_ids: list[str],
    ) -> dict[str, str]:
        """Return {document_id: raw_text} for each requested id that exists."""
        ...

    async def get_neighbor_chunks(
        self,
        document_id: str,
        chunk_no: int,
        window: int,
    ) -> list[ChunkSearchResult]:
        """Return chunks with chunk_no in [chunk_no-window, chunk_no+window], ordered by chunk_no.

        Used by R7 OptionalEnrich to load surrounding context for a matched chunk.
        Returned chunks have rank=0.0 (positional retrieval, not BM25-ranked).
        The matched chunk itself is included in the result.
        """
        ...

    async def list_documents_by_date(
        self,
        *,
        limit: int = 5,
        category: Category | None = None,
    ) -> list[DocumentMetadata]:
        """Return most recent documents ordered by document_date (with indexed_at fallback).

        Returns up to `limit` documents, optionally filtered by category.
        Sorted by COALESCE(document_date, indexed_at) DESC (most recent first).
        """
        ...

    async def get_document_chunks(
        self,
        document_id: str,
        limit: int,
    ) -> list[ChunkSearchResult]:
        """Return first N chunks of a document ordered by chunk_no (ascending).

        Used by recency bundle to fetch initial chunks from recent documents.
        Returned chunks have rank=0.0 (positional retrieval, not BM25-ranked).
        """
        ...
