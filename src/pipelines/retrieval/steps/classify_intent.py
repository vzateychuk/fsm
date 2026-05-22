from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import ClassVar

from fsm.core import RunContext

from pipelines.retrieval.config import RetrievalConfig
from pipelines.retrieval.models import IntentInfo, RetrievalData, RetrieveRequest

@dataclass(slots=True)
class ClassifyIntent:
    """R2: Propagate explicit category from request into pipeline intent.

    Wraps request.category in IntentInfo so downstream steps have a uniform
    intent contract regardless of how the category was obtained (UI selection,
    API caller, etc.). No keyword heuristics are applied: the caller is
    responsible for determining the category. This keeps the pipeline
    deterministic and avoids false-positive category detection that would
    silently narrow search results.

    In RETRIEVE_CATEGORY_MODE=hard the detected_type becomes a SQL WHERE
    filter in R5, restricting results to one category. In soft mode (default)
    it is available for debug only and has no effect on ranking or filtering.

    If request.category is None, intent remains None and R5 searches across
    all categories.

    Reads: ctx.input.category
    Sets:  ctx.data.intent
    """

    id: ClassVar[str] = "classify_intent"
    desc: ClassVar[str] = "R2: Propagate request category into pipeline intent"
    config: RetrievalConfig

    async def run(self, ctx: RunContext[RetrieveRequest, RetrievalData]) -> None:
        if ctx.input.category is not None:
            ctx.data.intent = IntentInfo(
                detected_type=ctx.input.category,
                confidence=1.0,
                matched_keywords=[],
            )
        else:
            ctx.data.intent = None
