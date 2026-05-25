"""C3: Call medical LLM to answer patient query."""

from typing import ClassVar

from src.fsm.core import RunContext
from src.llm.llm_client import LLMClient
from src.llm.models import ChatRequest, Message
from src.common.patient import PatientInfo
from src.pipelines.consult.models import ConsultData, ConsultRequest


class CallPatientQuery:
    """C3: Answer patient query with medical LLM."""

    id: ClassVar[str] = "call_patient_query"
    desc: ClassVar[str] = "C3: Answer patient query with medical LLM"

    def __init__(
        self,
        llm_client: LLMClient,
        system_prompt: str,
        user_prompt_template: str,
        patient_config: PatientInfo,
    ) -> None:
        self.llm_client = llm_client
        self.system_prompt = system_prompt
        self.user_prompt_template = user_prompt_template
        self.patient_config = patient_config

    async def run(self, runCtx: RunContext[ConsultRequest, ConsultData]) -> None:
        bundle = runCtx.data.bundle
        if bundle is None:
            runCtx.data.raw_answer = ""
            return

        top_chunks_text = "\n\n".join(bundle.top_chunks)
        kb_excerpts_text = "\n\n".join(bundle.kb_excerpts)
        patient_info_text = self._format_patient_info()

        user_msg = self.user_prompt_template.format(
            patient_info=patient_info_text,
            user_request=runCtx.data.user_request,
            top_chunks=top_chunks_text,
            kb_excerpts=kb_excerpts_text,
        )

        request = ChatRequest(
            messages=[
                Message("system", self.system_prompt),
                Message("user", user_msg),
            ]
        )

        response = await self.llm_client.chat(request)
        runCtx.data.raw_answer = response.text

    def _format_patient_info(self) -> str:
        """Format patient demographic and clinical information."""
        lines = [
            f"Age: {self.patient_config.age} years",
            f"Sex: {self.patient_config.sex}",
        ]
        if self.patient_config.chronic_conditions:
            conditions = ", ".join(self.patient_config.chronic_conditions)
            lines.append(f"Chronic conditions: {conditions}")
        if self.patient_config.current_medications:
            meds = ", ".join(self.patient_config.current_medications)
            lines.append(f"Current medications: {meds}")
        if self.patient_config.allergies:
            allergies = ", ".join(self.patient_config.allergies)
            lines.append(f"Allergies: {allergies}")
        return "\n".join(lines)
