"""C1: Retrieve query and recency bundles from knowledge base."""

from datetime import date, timedelta
from typing import ClassVar

from src.fsm.core import RunContext
from src.pipelines.consult.config import ConsultConfig
from src.pipelines.consult.models import ConsultData, ConsultRequest
from src.pipelines.retrieval.models import RetrieveRequest
from src.pipelines.retrieval.runner import RetrievalRunner
from src.store.knowledge_store import KnowledgeStore


class Retrieve:
    """C1: Retrieve query and recency bundles."""

    id: ClassVar[str] = "retrieve"
    desc: ClassVar[str] = "C1: Retrieve query + recency bundles"

    def __init__(
        self,
        retrieval_runner: RetrievalRunner,
        store: KnowledgeStore,
        config: ConsultConfig,
    ) -> None:
        self.retrieval_runner = retrieval_runner
        self.store = store
        self.config = config

    async def run(self, ctx: RunContext[ConsultRequest, ConsultData]) -> None:
        # Query bundle: BM25-ranked retrieval
        retrieve_request = RetrieveRequest(
            query=ctx.data.user_request,
            limit=self.config.retrieval.query_top_k,
            limit_per_document=self.config.retrieval.query_limit_per_document,
        )
        retrieve_response = await self.retrieval_runner.run(retrieve_request)
        ctx.data.query_chunks = retrieve_response.chunks

        # Recency bundle: fresh documents + their first chunks
        today = date.today().isoformat()
        cutoff = (
            date.today() - timedelta(days=self.config.recency.max_age_days)
        ).isoformat()

        recent_docs_all = await self.store.list_documents_by_date(
            limit=self.config.recency.db_fetch_limit
        )

        recent_docs = [
            d
            for d in recent_docs_all
            if d.document_date and cutoff <= d.document_date <= today
        ][: self.config.recency.max_docs]

        for doc in recent_docs:
            chunks = await self.store.get_document_chunks(
                doc.document_id,
                self.config.recency.chunks_per_doc,
            )
            ctx.data.recency_chunks.extend(chunks)
