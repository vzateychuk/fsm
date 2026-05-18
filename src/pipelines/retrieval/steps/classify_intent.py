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

    If request.category is set, wraps it in IntentInfo with confidence=1.0.
    If not set, intent remains None — SearchChunks will search across all categories.
    No heuristic or keyword matching: category must be provided explicitly by the caller.
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

        if self.config.debug:
            ctx.data.debug["intent"] = {
                "category": ctx.input.category,
                "intent_set": ctx.data.intent is not None,
            }
