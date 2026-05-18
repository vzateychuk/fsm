from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import ClassVar

from fsm.core import RunContext
from pipelines.retrieval.models import RetrievalData, RetrieveRequest

@dataclass(slots=True)
class LoadRequest:
    """R0: Copy query from RetrieveRequest into pipeline state."""

    id: ClassVar[str] = "load_request"
    desc: ClassVar[str] = "R0: Load query from RetrieveRequest into pipeline state"

    async def run(self, ctx: RunContext[RetrieveRequest, RetrievalData]) -> None:
        ctx.data.desc = self.desc
        ctx.data.query_original = ctx.input.query
