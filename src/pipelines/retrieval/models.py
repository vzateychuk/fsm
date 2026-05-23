from __future__ import annotations

from dataclasses import dataclass, field

from pydantic import Field

from fsm.models import SagaData, SagaInput
from store.knowledge_store import ChunkSearchResult


# ---------------------------------------------------------------------------
# External API contracts (RetrieveRequest / RetrieveResponse)
# ---------------------------------------------------------------------------


class RetrieveRequest(SagaInput):
    """External input contract: accepted by RetrievalRunner, CLI, or API clients."""

    # Исходный текст запроса пользователя; нормализуется в R1 и передаётся дальше по pipeline
    query: str

    # Явное указание категории документа (значение из config/categories.yaml);
    # если задано, R2 ClassifyIntent использует это значение напрямую, без эвристики
    category: str | None = None

    # SQL-фильтр: ограничить поиск чанками одного конкретного документа по его document_id
    document_id: str | None = None

    # SQL-фильтр: вернуть только чанки, чей section_path начинается с этого префикса
    # (например, "Лечение > Медикаменты" вернёт все подразделы этого пути)
    section_path_prefix: str | None = None

    # SQL-фильтр: дата нижней границы документов (ISO формат YYYY-MM-DD, включающее);
    # если задано, возвращаются только чанки из документов, где document_date >= from_date
    from_date: str | None = None

    # SQL-фильтр: дата верхней границы документов (ISO формат YYYY-MM-DD, включающее);
    # если задано, возвращаются только чанки из документов, где document_date <= to_date
    to_date: str | None = None

    # Максимальное количество ChunkSearchResult в итоговом ответе (после применения diversity)
    limit: int = 20

    # Ограничение diversity: не более N чанков от одного документа в итоговом списке;
    # 0 отключает ограничение — все чанки из prelimit попадают в результат
    limit_per_document: int = 3

    # Количество результатов BM25, которые извлекаются до применения diversity-фильтра;
    # должен быть >= limit, чтобы diversity не обрезала результаты слишком рано
    prelimit: int = 200

    # Зарезервировано для R7 OptionalEnrich (Phase R3): количество соседних чанков
    # (до и после), которые будут добавлены к каждому найденному чанку для контекста;
    # 0 — отключено
    context_window: int = 0

    # Если True, R7 OptionalEnrich загружает raw_text из таблицы documents и записывает его
    # в DocumentEvidence.full_text для каждого найденного документа
    include_full_docs: bool = False


@dataclass
class DocumentEvidence:
    """Retrieval result grouped by document: document metadata + matched chunks.

    context_chunks: populated by R7 when context_window > 0.
    Maps chunk_id → ordered list of neighboring chunks (chunk_no ± window).
    The matched chunk itself is excluded from its own neighbor list.
    """

    document_id: str
    source_path: str
    category: str
    chunks: list[ChunkSearchResult] = field(default_factory=list)
    full_text: str | None = None
    context_chunks: dict[str, list[ChunkSearchResult]] = field(default_factory=dict)


@dataclass
class RetrieveResponse:
    """External response contract returned by RetrievalRunner."""

    query_original: str
    query_normalized: str
    fts_match: str
    chunks: list[ChunkSearchResult]
    documents: list[DocumentEvidence]


# ---------------------------------------------------------------------------
# Internal types
# ---------------------------------------------------------------------------


@dataclass
class IntentInfo:
    """Result of intent detection (step R2 ClassifyIntent).

    detected_type: canonical category from config/categories.yaml, or None if not specified
    confidence: always 1.0 (set from explicit category field on request)
    matched_keywords: always empty (no heuristic — category comes from request directly)
    """

    detected_type: str | None
    confidence: float
    matched_keywords: list[str]


@dataclass
class QueryPlan:
    """Internal pipeline object built from RetrieveRequest and mutated by steps R1–R4.

    Not returned in the response and not persisted to DB.
    fts_match is the only field passed to KnowledgeStore.search_chunks().

    Invariants before calling search_chunks():
    - fts_match is not empty
    - limit > 0, prelimit >= limit
    """

    query_original: str
    query_normalized: str = ""
    intent: IntentInfo | None = None
    expanded_terms: list[str] = field(default_factory=list)
    fts_match: str = ""                        # FTS5 MATCH expression; the only string → store
    category: str | None = None                # SQL filter (from request.category)
    document_id: str | None = None             # SQL filter
    kinds: set[str] | None = None              # SQL filter
    section_path_prefix: str | None = None     # SQL filter
    limit: int = 20
    prelimit: int = 200
    limit_per_document: int = 3                # 0 = diversity disabled


# ---------------------------------------------------------------------------
# Pipeline state (FSM context data)
# ---------------------------------------------------------------------------


class RetrievalData(SagaData):
    """Pipeline state data for retrieval FSM.

    Field invariants (guaranteed after the respective step completes):
    - R0 LoadRequest:      query_original is not None
    - R1 NormalizeQuery:   query_normalized is not None
    - R2 ClassifyIntent:   intent may be None (valid when category not specified in request)
    - R3 ExpandAliases:    expanded_terms has len >= 1
    - R4 BuildFtsQuery:    fts_match is not empty; safe FTS5 MATCH string
    - R5 SearchChunks:     final_chunks populated (may be empty if no results)
    - R6 GroupByDocument:  documents populated (grouped final_chunks by document_id)
    """

    model_config = {"arbitrary_types_allowed": True}

    # R0 LoadRequest
    query_original: str | None = None

    # R1 NormalizeQuery
    query_normalized: str | None = None

    # R2 ClassifyIntent
    intent: IntentInfo | None = None

    # R3 ExpandAliases
    expanded_terms: list[str] = Field(default_factory=list)

    # R4 BuildFtsQuery
    # None until R4 completes; R5 SearchChunks must assert this is not None/empty before calling store
    fts_match: str | None = None

    # R5 SearchChunks
    final_chunks: list[ChunkSearchResult] = Field(default_factory=list)

    # R6 GroupByDocument
    documents: list[DocumentEvidence] = Field(default_factory=list)
