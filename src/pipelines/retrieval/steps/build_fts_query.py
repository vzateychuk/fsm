from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from fsm.core import RunContext

from pipelines.retrieval.config import RetrievalConfig
from pipelines.retrieval.fts_query import build_fts_match
from pipelines.retrieval.models import RetrievalData, RetrieveRequest


@dataclass(slots=True)
class BuildFtsQuery:
    """R4: Build safe FTS5 MATCH string from expanded terms."""

    id: ClassVar[str] = "build_fts_query"
    desc: ClassVar[str] = "R4: Build safe FTS5 MATCH string"
    config: RetrievalConfig

    async def run(self, ctx: RunContext[RetrieveRequest, RetrievalData]) -> None:
        ctx.data.fts_match = build_fts_match(ctx.data.expanded_terms, self.config)
        if self.config.debug:
            ctx.data.debug["fts_match"] = {
                "query": ctx.data.fts_match,
                "enable_prefixes": self.config.enable_prefixes,
                "prefix_min_len": self.config.prefix_min_len,
            }

