"""C1: Retrieve query and recency bundles from knowledge base."""

from datetime import date, timedelta
from typing import ClassVar

from src.fsm.core import RunContext
from src.pipelines.consult.config import ConsultConfig
from src.pipelines.consult.models import ConsultData, ConsultRequest
from src.pipelines.retrieval.config import RetrievalConfig
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
        retrieval_config: RetrievalConfig,
        store: KnowledgeStore,
        consult_config: ConsultConfig,
    ) -> None:
        self.retrieval_runner = retrieval_runner
        self.retrieval_config = retrieval_config
        self.store = store
        self.consult_config = consult_config

    async def run(self, runCtx: RunContext[ConsultRequest, ConsultData]) -> None:
        # Query bundle: BM25-ranked retrieval
        retrieve_request = RetrieveRequest(
            query=runCtx.data.user_request,
            limit=self.consult_config.retrieval.query_top_k,
            limit_per_document=self.consult_config.retrieval.query_limit_per_document,
            prelimit=self.retrieval_config.prelimit,
        )
        retrieve_response = await self.retrieval_runner.run(retrieve_request)
        runCtx.data.query_chunks = retrieve_response.chunks

        # Recency bundle: fresh documents + their first chunks
        today = date.today().isoformat()
        cutoff = (
            date.today() - timedelta(days=self.consult_config.recency.max_age_days)
        ).isoformat()

        recent_docs_all = await self.store.list_documents_by_date(
            limit=self.consult_config.recency.db_fetch_limit
        )

        recent_docs = [
            d
            for d in recent_docs_all
            if d.document_date and cutoff <= d.document_date <= today
        ][: self.consult_config.recency.max_docs]

        for doc in recent_docs:
            chunks = await self.store.get_document_chunks(
                doc.document_id,
                self.consult_config.recency.chunks_per_doc,
            )
            runCtx.data.recency_chunks.extend(chunks)
