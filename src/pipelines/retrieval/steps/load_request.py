from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import ClassVar

from fsm.core import RunContext
from pipelines.retrieval.models import RetrievalData, RetrieveRequest

@dataclass(slots=True)
class LoadRequest:
    """R0: Transfer query from immutable RetrieveRequest into mutable pipeline state.

    RetrieveRequest is the immutable input contract; RetrievalData is the mutable
    pipeline state that accumulates results step by step. This step initialises the
    state with the original query string so downstream steps can read and transform
    it without touching the input object directly.

    Sets: ctx.data.query_original
    """

    id: ClassVar[str] = "load_request"
    desc: ClassVar[str] = "R0: Load query from RetrieveRequest into pipeline state"

    async def run(self, ctx: RunContext[RetrieveRequest, RetrievalData]) -> None:
        ctx.data.desc = self.desc
        ctx.data.query_original = ctx.input.query
