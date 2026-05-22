from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from common.normalizer import normalize_text
from fsm.core import RunContext
from pipelines.retrieval.models import RetrievalData, RetrieveRequest


@dataclass(slots=True)
class NormalizeQuery:
    """R1: Normalize query text to match the FTS index encoding.

    The ingest pipeline stores chunk text in normalized form (NFKC, lowercase,
    ё→е). Without the same normalization on the query side, tokens may fail to
    match their indexed counterparts due to Unicode variants, mixed case, or
    ё/е ambiguity. This step applies the same normalizer (common.normalizer)
    as ingest step S1 PreprocessText, keeping query vocabulary in sync with
    the index.

    Reads: ctx.data.query_original
    Sets:  ctx.data.query_normalized
    """

    id: ClassVar[str] = "normalize_query"
    desc: ClassVar[str] = "R1: Normalize query text"

    async def run(self, ctx: RunContext[RetrieveRequest, RetrievalData]) -> None:
        raw = ctx.data.query_original or ""
        ctx.data.query_normalized = normalize_text(raw).strip()
