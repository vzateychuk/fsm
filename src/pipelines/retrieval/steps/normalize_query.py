from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from common.normalizer import normalize_text
from fsm.core import RunContext
from pipelines.retrieval.models import RetrievalData, RetrieveRequest


@dataclass(slots=True)
class NormalizeQuery:
    """R1: Normalize query text (NFKC + lowercase + ё→е + strip)."""

    id: ClassVar[str] = "normalize_query"
    desc: ClassVar[str] = "R1: Normalize query text"

    async def run(self, ctx: RunContext[RetrieveRequest, RetrievalData]) -> None:
        raw = ctx.data.query_original or ""
        ctx.data.query_normalized = normalize_text(raw).strip()
