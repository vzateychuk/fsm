"""C4: Format final response."""

from typing import ClassVar

from src.fsm.core import RunContext
from src.pipelines.consult.models import ConsultData, ConsultRequest, ConsultResponse


class FormatResponse:
    """C4: Format response for output."""

    id: ClassVar[str] = "format_response"
    desc: ClassVar[str] = "C4: Format response"

    async def run(self, ctx: RunContext[ConsultRequest, ConsultData]) -> None:
        ctx.data.response = ConsultResponse(raw_text=ctx.data.raw_answer)
