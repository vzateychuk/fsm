from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import ClassVar

from fsm.core import RunContext

logger = logging.getLogger(__name__)
from pipelines.retrieval.config import RetrievalConfig
from pipelines.retrieval.models import RetrievalData, RetrieveRequest
from store.knowledge_store import KnowledgeStore


@dataclass(slots=True)
class SearchChunks:
    """R5: Execute FTS5 BM25 search with oversampling and per-document diversity.

    This is the core retrieval step. It submits the prepared fts_match
    expression to KnowledgeStore.search_chunks(), which runs a BM25-ranked
    FTS5 query with field weights (tags_text > heading > section_path > text)
    and returns chunks ordered by relevance score.

    Oversampling (prelimit >> limit) ensures the diversity filter has enough
    candidates: the store first collects up to prelimit BM25 results, then
    applies a cap of limit_per_document chunks per document, and finally
    returns the top limit results. Without oversampling, a single highly
    relevant document could exhaust the result set before other documents
    get a chance to appear.

    category filtering:
    - "soft" (default): category is not used as a SQL filter; search spans
      all documents. Suitable when a diagnostic procedure may appear in both
      diagnostic and consultation documents.
    - "hard": if intent.detected_type is set, adds WHERE d.category = ?
      to restrict results to one document category.

    Reads: ctx.data.fts_match, ctx.data.intent, ctx.input.*
    Sets:  ctx.data.final_chunks
    """

    id: ClassVar[str] = "search_chunks"
    desc: ClassVar[str] = "R5: Query KnowledgeStore with BM25 and diversity"
    store: KnowledgeStore
    config: RetrievalConfig

    async def run(self, ctx: RunContext[RetrieveRequest, RetrievalData]) -> None:
        ctx.data.desc = self.desc

        # Prepare search parameters from request
        category: str | None = None
        if self.config.category_mode == "hard" and ctx.data.intent is not None:
            category = ctx.data.intent.detected_type

        # Build kinds filter if specified in request
        kinds: set[str] | None = None
        if ctx.input.section_path_prefix:
            # This would filter by section; kinds filtering is optional here
            pass

        # Execute search with diversity
        ctx.data.final_chunks = await self.store.search_chunks(
            query=ctx.data.fts_match or "",
            category=category,
            document_id=ctx.input.document_id,
            kinds=kinds,
            section_path_prefix=ctx.input.section_path_prefix,
            limit=ctx.input.limit,
            limit_per_document=ctx.input.limit_per_document,
            prelimit=ctx.input.prelimit,
            bm25_weights=self.config.bm25_weights,
        )

        if self.config.debug:
            ctx.data.debug["search_chunks"] = {
                "fts_query": ctx.data.fts_match or "",
                "category_mode": self.config.category_mode,
                "category_filter_applied": category,
                "diversity_limit_per_doc": ctx.input.limit_per_document,
                "final_limit": ctx.input.limit,
                "prelimit": ctx.input.prelimit,
                "results_count": len(ctx.data.final_chunks),
                "top_rank": ctx.data.final_chunks[0].rank if ctx.data.final_chunks else None,
                "results_by_doc": {},
            }
            # Count results per document for debug
            by_doc = {}
            for chunk in ctx.data.final_chunks:
                by_doc.setdefault(chunk.document_id, 0)
                by_doc[chunk.document_id] += 1
            ctx.data.debug["search_chunks"]["results_by_doc"] = by_doc
            logger.debug(
                "[R5] search_chunks: fts=%r category=%r results=%d top_rank=%s by_doc=%s",
                ctx.data.fts_match or "",
                category,
                len(ctx.data.final_chunks),
                ctx.data.final_chunks[0].rank if ctx.data.final_chunks else None,
                by_doc,
            )
