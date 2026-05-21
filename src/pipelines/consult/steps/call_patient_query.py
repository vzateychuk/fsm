"""C3: Call medical LLM to answer patient query."""

from typing import ClassVar

from src.fsm.core import RunContext
from src.llm.llm_client import LLMClient
from src.llm.models import ChatRequest, Message
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
    ) -> None:
        self.llm_client = llm_client
        self.system_prompt = system_prompt
        self.user_prompt_template = user_prompt_template

    async def run(self, ctx: RunContext[ConsultRequest, ConsultData]) -> None:
        bundle = ctx.data.bundle
        if bundle is None:
            ctx.data.raw_answer = ""
            return

        top_chunks_text = "\n\n".join(bundle.top_chunks)
        kb_excerpts_text = "\n\n".join(bundle.kb_excerpts)
        provenance_text = "\n".join(bundle.provenance)

        user_msg = self.user_prompt_template.format(
            top_chunks=top_chunks_text,
            user_request=ctx.data.user_request,
            kb_excerpts=kb_excerpts_text,
            provenance=provenance_text,
        )

        request = ChatRequest(
            messages=[
                Message("system", self.system_prompt),
                Message("user", user_msg),
            ]
        )

        response = await self.llm_client.chat(request)
        ctx.data.raw_answer = response.text
