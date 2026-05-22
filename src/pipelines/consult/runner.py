"""ConsultRunner — orchestrates the consultation FSM."""

from __future__ import annotations

from pathlib import Path

from src.fsm.core import RunContext, SagaDefinition
from src.fsm.saga import Saga
from src.llm.llm_client import LLMClient
from src.pipelines.consult.config import ConsultConfig, PatientInfo
from src.pipelines.consult.models import ConsultData, ConsultRequest, ConsultResponse
from src.pipelines.consult.steps import (
    BuildBundle,
    CallPatientQuery,
    FormatResponse,
    LoadRequest,
    Retrieve,
)
from src.pipelines.retrieval.config import RetrievalConfig
from src.pipelines.retrieval.runner import RetrievalRunner
from src.store.knowledge_store import KnowledgeStore


class ConsultRunner:
    """Orchestrates the consultation FSM for a single ConsultRequest.

    Wires steps C0–C4 and executes them in sequence.

    Usage:
        consult_config = ConsultConfig.load("config/consult.yaml")
        retrieval_config = RetrievalConfig.load("config/retrieve.yaml")
        retrieval_runner = RetrievalRunner(store, retrieval_config)
        runner = ConsultRunner(
            retrieval_runner=retrieval_runner,
            retrieval_config=retrieval_config,
            store=knowledge_store,
            llm_client=llm_client,
            consult_config=consult_config,
            prompts_dir=Path("prompts"),
        )
        result = await runner.run(ConsultRequest(user_request="..."))
    """

    def __init__(
        self,
        retrieval_runner: RetrievalRunner,
        retrieval_config: RetrievalConfig,
        store: KnowledgeStore,
        llm_client: LLMClient,
        consult_config: ConsultConfig,
        prompts_dir: Path,
    ) -> None:
        system_prompt = (prompts_dir / "consult" / "system.md").read_text(
            encoding="utf-8"
        )
        user_prompt_template = (prompts_dir / "consult" / "user.md").read_text(
            encoding="utf-8"
        )
        patient_config = PatientInfo.load(prompts_dir.parent / "config" / "patient.yaml")

        self._definition: SagaDefinition[ConsultRequest, ConsultData] = SagaDefinition(
            name="consult",
            steps=[
                LoadRequest(),
                Retrieve(retrieval_runner, retrieval_config, store, consult_config),
                BuildBundle(consult_config),
                CallPatientQuery(llm_client, system_prompt, user_prompt_template, patient_config),
                FormatResponse(),
            ],
        )

    async def run(self, request: ConsultRequest) -> ConsultData:
        """Execute the consultation pipeline.

        Args:
            request: ConsultRequest with user_request field.

        Returns:
            ConsultData with assembled bundle and LLM response.
        """
        import uuid

        saga = Saga(definition=self._definition)
        runCtx = RunContext(
            run_id=f"consult-{uuid.uuid4().hex[:8]}",
            saga_name="consult",
            cursor=0,
            input=request,
            data=ConsultData(),
        )
        await saga.run(runCtx)
        return runCtx.data
