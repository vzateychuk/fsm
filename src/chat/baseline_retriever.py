"""BaselineRetriever — builds the initial KB context bundle for each chat turn."""

from datetime import date, timedelta

from src.chat.config import ChatConfig
from src.common.bundle_builder import KBContextBundle, KBContextBundleBuilder
from src.pipelines.retrieval.config import RetrievalConfig
from src.pipelines.retrieval.models import RetrieveRequest
from src.pipelines.retrieval.runner import RetrievalRunner
from src.store.knowledge_store import ChunkSearchResult, KnowledgeStore


class BaselineRetriever:
    """Builds the baseline KB context bundle for each patient turn.

    Combines two retrieval strategies:
    - Query bundle: BM25-ranked search over the full KB within a lookback window.
    - Recency bundle: first chunks of the N most recent documents regardless of
      query relevance, ensuring fresh records (test results, discharge summaries)
      are always visible to the LLM.

    Called once per patient turn before constructing the user message.
    """

    def __init__(
        self,
        retrieval_runner: RetrievalRunner,
        store: KnowledgeStore,
        retrieval_config: RetrievalConfig,
        chat_config: ChatConfig,
    ) -> None:
        self._runner = retrieval_runner
        self._store = store
        self._retrieval_config = retrieval_config
        self._recency_cfg = chat_config.recency
        self._bundle_builder = KBContextBundleBuilder(
            bundle_config=chat_config.bundle,
            excerpts_config=chat_config.excerpts,
        )

    async def run(self, query: str) -> KBContextBundle:
        """Build baseline context bundle for a patient query.

        Args:
            query: Patient's free-text complaint or question.

        Returns:
            KBContextBundle with top_chunks and kb_excerpts ready for prompt formatting.
        """
        query_chunks = await self._fetch_query_bundle(query)
        recency_chunks = await self._fetch_recency_bundle()
        return self._bundle_builder.build(query_chunks, recency_chunks)

    async def _fetch_query_bundle(self, query: str) -> list[ChunkSearchResult]:
        today = date.today()
        from_date = (today - timedelta(days=self._retrieval_config.lookback_days)).isoformat()
        to_date = today.isoformat()

        request = RetrieveRequest(
            query=query,
            limit=self._retrieval_config.query_top_k,
            limit_per_document=self._retrieval_config.query_limit_per_document,
            prelimit=self._retrieval_config.prelimit,
            from_date=from_date,
            to_date=to_date,
        )
        response = await self._runner.run(request)
        return response.chunks  # type: ignore[no-any-return]

    async def _fetch_recency_bundle(self) -> list[ChunkSearchResult]:
        today = date.today()
        from_date = (today - timedelta(days=self._retrieval_config.lookback_days)).isoformat()

        recent_docs_all = await self._store.list_documents_by_date(
            limit=self._recency_cfg.db_fetch_limit
        )
        recent_docs = [
            doc for doc in recent_docs_all if doc.document_date >= from_date
        ][: self._recency_cfg.max_docs]

        recency_chunks: list[ChunkSearchResult] = []
        for doc in recent_docs:
            chunks = await self._store.get_document_chunks(
                doc.document_id,
                self._recency_cfg.chunks_per_doc,
            )
            recency_chunks.extend(chunks)
        return recency_chunks
