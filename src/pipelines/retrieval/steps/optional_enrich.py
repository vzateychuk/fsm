from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from fsm.core import RunContext
from pipelines.retrieval.config import RetrievalConfig
from pipelines.retrieval.models import RetrievalData, RetrieveRequest
from store.knowledge_store import KnowledgeStore


@dataclass(slots=True)
class OptionalEnrich:
    """R7: Optionally load full document text.

    When include_full_docs=True, fetches raw_text from the documents table
    for every DocumentEvidence in ctx.data.documents and stores it in
    DocumentEvidence.full_text.
    """

    id: ClassVar[str] = "optional_enrich"
    desc: ClassVar[str] = "R7: Optionally load context window or full documents"
    store: KnowledgeStore
    config: RetrievalConfig

    async def run(self, ctx: RunContext[RetrieveRequest, RetrievalData]) -> None:
        if not ctx.input.include_full_docs or not ctx.data.documents:
            return

        doc_ids = [doc.document_id for doc in ctx.data.documents]
        raw_texts = await self.store.get_documents_raw_text(doc_ids)

        for doc in ctx.data.documents:
            doc.full_text = raw_texts.get(doc.document_id)
