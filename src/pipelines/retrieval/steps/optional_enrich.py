from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from fsm.core import RunContext
from pipelines.retrieval.config import RetrievalConfig
from pipelines.retrieval.models import RetrievalData, RetrieveRequest
from store.knowledge_store import KnowledgeStore


@dataclass(slots=True)
class OptionalEnrich:
    """R7: Optionally load full document text for each matched document.

    By default retrieval returns only matched chunks — short, targeted
    fragments that are sufficient for most LLM prompts. However, when an
    orchestrator or agent needs the complete document (e.g. to summarise an
    entire consultation, provide full medical record context, or
    cross-reference findings across sections), it sets include_full_docs=True.

    When enabled, this step calls KnowledgeStore.get_documents_raw_text() to
    fetch raw_text from the documents table in SQLite for each unique
    DocumentEvidence. The result is written to DocumentEvidence.full_text and
    returned as part of RetrieveResponse. If a document has no raw_text stored
    (edge case during ingest), full_text remains None.

    If include_full_docs=False (default) or ctx.data.documents is empty,
    this step is a no-op.

    Reads: ctx.input.include_full_docs, ctx.data.documents
    Sets:  DocumentEvidence.full_text for each document in ctx.data.documents
    """

    id: ClassVar[str] = "optional_enrich"
    desc: ClassVar[str] = "R7: Optionally load context window or full documents"
    store: KnowledgeStore
    config: RetrievalConfig

    async def run(self, ctx: RunContext[RetrieveRequest, RetrievalData]) -> None:
        if not ctx.data.documents:
            return

        if ctx.input.include_full_docs:
            doc_ids = [doc.document_id for doc in ctx.data.documents]
            raw_texts = await self.store.get_documents_raw_text(doc_ids)
            for doc in ctx.data.documents:
                doc.full_text = raw_texts.get(doc.document_id)

        if ctx.input.context_window > 0:
            for doc in ctx.data.documents:
                for chunk in doc.chunks:
                    neighbors = await self.store.get_neighbor_chunks(
                        document_id=chunk.document_id,
                        chunk_no=chunk.chunk_no,
                        window=ctx.input.context_window,
                    )
                    doc.context_chunks[chunk.chunk_id] = [
                        n for n in neighbors if n.chunk_id != chunk.chunk_id
                    ]
