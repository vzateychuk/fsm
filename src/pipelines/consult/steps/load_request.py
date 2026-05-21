"""C0: Load user request into pipeline state."""

from typing import ClassVar

from src.fsm.core import RunContext
from src.pipelines.consult.models import ConsultData, ConsultRequest


class LoadRequest:
    """C0: Copy user_request from input to pipeline state."""

    id: ClassVar[str] = "load_request"
    desc: ClassVar[str] = "C0: Load request into state"

    async def run(self, ctx: RunContext[ConsultRequest, ConsultData]) -> None:
        request: ConsultRequest = ctx.input
        ctx.data.user_request = request.user_request
        ctx.data.desc = self.desc
