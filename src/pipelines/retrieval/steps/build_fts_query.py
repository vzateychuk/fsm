from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from fsm.core import RunContext

from pipelines.retrieval.config import RetrievalConfig
from pipelines.retrieval.fts_query import build_fts_match
from pipelines.retrieval.models import RetrievalData, RetrieveRequest


@dataclass(slots=True)
class BuildFtsQuery:
    """R4: Build a safe, well-formed FTS5 MATCH expression from expanded terms.

    FTS5 has its own query syntax where characters like quotes, parentheses,
    and hyphens act as operators. Passing user input directly causes parse
    errors or unexpected query semantics. This step:
    - Escapes FTS5 special characters in each token.
    - Optionally appends a prefix wildcard (*) to Cyrillic tokens of
      sufficient length (>= prefix_min_len from config) so that "протруз*"
      matches "протрузия", "протрузии", etc., improving recall for inflected
      word forms common in Russian medical text.
    - Joins all tokens with OR so any matching term contributes to BM25 score.

    The resulting fts_match string is the only query artefact passed to
    KnowledgeStore. It is also returned in RetrieveResponse for debugging.

    Reads: ctx.data.expanded_terms, config.enable_prefixes, config.prefix_min_len
    Sets:  ctx.data.fts_match
    """

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

