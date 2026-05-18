from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, Protocol

if TYPE_CHECKING:
    from pipelines.ingest.models import ChunkTagged

Category = str
ChunkKind = Literal["table", "list", "fact", "section"]


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
        limit: int = 20,
        limit_per_document: int = 3,
        prelimit: int = 200,
    ) -> list[ChunkSearchResult]: ...

    async def get_documents_raw_text(
        self,
        document_ids: list[str],
    ) -> dict[str, str]:
        """Return {document_id: raw_text} for each requested id that exists."""
        ...
