from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from fsm.core import RunContext
from pipelines.retrieval.models import RetrievalData, RetrieveRequest


@dataclass(slots=True)
class GroupByDocument:
    """R6: Group final_chunks by document_id into DocumentEvidence list.

    Takes ctx.data.final_chunks (already sorted by rank, post-diversity from R5)
    and groups them by document_id, preserving order within each document.
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
