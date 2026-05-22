"""RetrievalRunner — wires the retrieval FSM and executes it.

Retrieval is a stateless read-only query: no checkpointing is needed.
The runner uses Saga directly (without SagaRunner) to run steps R0–R7
and builds a RetrieveResponse from the final pipeline state.
"""

from __future__ import annotations

import uuid

from fsm.core import RunContext, SagaDefinition
from fsm.saga import Saga
from pipelines.retrieval.config import RetrievalConfig
from pipelines.retrieval.models import (
    RetrievalData,
    RetrieveRequest,
    RetrieveResponse,
)
from pipelines.retrieval.steps import (
    BuildFtsQuery,
    ClassifyIntent,
    ExpandAliases,
    GroupByDocument,
    LoadRequest,
    NormalizeQuery,
    OptionalEnrich,
    SearchChunks,
)
from store.knowledge_store import KnowledgeStore


class RetrievalRunner:
    """Orchestrates the retrieval FSM for a single RetrieveRequest.

    Usage:
        config = RetrievalConfig.from_config(config_dict)
        runner = RetrievalRunner(store=knowledge_store, config=config)
        response = await runner.run(RetrieveRequest(query="протрузия"))
    """

    def __init__(self, store: KnowledgeStore, config: RetrievalConfig) -> None:
        self._config = config
        self._definition: SagaDefinition[RetrieveRequest, RetrievalData] = SagaDefinition(
            name="retrieval",
            steps=[
                LoadRequest(),
                NormalizeQuery(),
                ClassifyIntent(config=config),
                ExpandAliases(config=config),
                BuildFtsQuery(config=config),
                SearchChunks(store=store, config=config),
                GroupByDocument(),
                OptionalEnrich(store=store, config=config),
            ],
        )
        self._saga: Saga[RetrieveRequest, RetrievalData] = Saga(self._definition)

    async def run(self, request: RetrieveRequest) -> RetrieveResponse:
        """Execute the full retrieval pipeline and return the response."""
        ctx: RunContext[RetrieveRequest, RetrievalData] = RunContext(
            run_id=f"retrieval-{uuid.uuid4().hex[:8]}",
            saga_name="retrieval",
            cursor=0,
            input=request,
            data=RetrievalData(),
        )
        await self._saga.run(ctx)
        return self._build_response(ctx.data)

    def _build_response(self, data: RetrievalData) -> RetrieveResponse:
        return RetrieveResponse(
            query_original=data.query_original or "",
            query_normalized=data.query_normalized or "",
            fts_match=data.fts_match or "",
            chunks=list(data.final_chunks),
            documents=list(data.documents),
        )
