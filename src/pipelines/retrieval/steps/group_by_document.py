from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from fsm.core import RunContext
from pipelines.retrieval.models import RetrievalData, RetrieveRequest


@dataclass(slots=True)
class GroupByDocument:
    """R6: Group ranked chunks by document to produce DocumentEvidence objects.

    R5 returns a flat list of chunks sorted by BM25 rank. For a useful
    retrieval response, chunks need to be grouped by their source document
    so the caller sees a coherent view: "document X matched with these N
    relevant fragments", rather than a disconnected list of text snippets.

    Grouping preserves BM25 rank order within each group (chunks from the
    same document appear in the order they were ranked). The first document
    in ctx.data.documents is the one whose best-ranked chunk had the highest
    relevance score.

    This step is intentionally lightweight: diversity has already been applied
    inside KnowledgeStore.search_chunks() in R5. R6 only restructures the
    existing data for consumption by the caller or by R7 OptionalEnrich.

    Reads: ctx.data.final_chunks
    Sets:  ctx.data.documents
    """

    id: ClassVar[str] = "group_by_document"
    desc: ClassVar[str] = "R6: Group result chunks by document_id"

    async def run(self, ctx: RunContext[RetrieveRequest, RetrievalData]) -> None:
        ctx.data.desc = self.desc

        from pipelines.retrieval.models import DocumentEvidence

        groups: dict[str, DocumentEvidence] = {}
        for chunk in ctx.data.final_chunks:
            if chunk.document_id not in groups:
                groups[chunk.document_id] = DocumentEvidence(
                    document_id=chunk.document_id,
                    source_path=chunk.source_path,
                    category=chunk.category,
                    chunks=[],
                )
            groups[chunk.document_id].chunks.append(chunk)

        ctx.data.documents = list(groups.values())

        # Add debug info about grouping
        if "search_chunks" in ctx.data.debug:
            ctx.data.debug["group_by_document"] = {
                "documents_count": len(ctx.data.documents),
                "docs_with_chunks": [
                    {
                        "document_id": doc.document_id,
                        "category": doc.category,
                        "chunks_count": len(doc.chunks),
                    }
                    for doc in ctx.data.documents
                ],
            }
