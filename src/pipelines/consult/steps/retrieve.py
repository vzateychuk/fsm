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
        # Create base retrieve request
        retrieve_request = RetrieveRequest(
            query=runCtx.data.user_request,
            limit=self.consult_config.retrieval.query_top_k,
            limit_per_document=self.consult_config.retrieval.query_limit_per_document,
            prelimit=self.retrieval_config.prelimit,
        )

        # Compute from_date and to_date: use explicit values from request, or defaults from config
        today = date.today().isoformat()
        from_date = runCtx.input.from_date or (
            date.today() - timedelta(days=self.consult_config.retrieval.lookback_days)
        ).isoformat()
        to_date = runCtx.input.to_date or today

        # Query bundle: BM25-ranked retrieval with computed date range
        retrieve_request.from_date = from_date
        retrieve_request.to_date = to_date
        retrieve_response = await self.retrieval_runner.run(retrieve_request)
        runCtx.data.query_chunks = retrieve_response.chunks

        # Recency bundle: fetch recent documents and extract their first chunks
        recent_docs_all = await self.store.list_documents_by_date(
            limit=self.consult_config.recency.db_fetch_limit
        )
        recent_docs = recent_docs_all[: self.consult_config.recency.max_docs]

        for doc in recent_docs:
            chunks = await self.store.get_document_chunks(
                doc.document_id,
                self.consult_config.recency.chunks_per_doc,
            )
            runCtx.data.recency_chunks.extend(chunks)
