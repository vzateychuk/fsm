from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import ClassVar

from fsm.core import RunContext

from pipelines.retrieval.alias_map import ALIAS_MAP
from pipelines.retrieval.config import RetrievalConfig
from pipelines.retrieval.models import RetrievalData, RetrieveRequest


@dataclass(slots=True)
class ExpandAliases:
    """R3: Expand query terms via alias map with OR semantics to improve recall.

    Medical documents use mixed notation: abbreviations (птг, пса, лпнп),
    transliterations (фгдс, эгдс), and full terms (паратгормон, psa, ldl)
    appear interchangeably. A query using only one notation misses documents
    written in another.

    This step applies the same alias map used during ingest (see ingest S7
    Tagging) to expand each token to all known synonyms, joining them with OR
    semantics so any matching form contributes to relevance score.
    Example: "птг" → ["птг", "паратгормон", "pth"].

    The expanded list is ordered (original token first, then its aliases) and
    deduplicated. It is passed to R4 which assembles the FTS5 MATCH string.

    Reads: ctx.data.query_normalized
    Sets:  ctx.data.expanded_terms
    """

    id: ClassVar[str] = "expand_aliases"
    desc: ClassVar[str] = "R3: Expand query terms via alias map (OR)"
    config: RetrievalConfig

    async def run(self, ctx: RunContext[RetrieveRequest, RetrievalData]) -> None:
        query = ctx.data.query_normalized or ""
        tokens = query.split()

        seen: set[str] = set()
        result: list[str] = []
        for token in tokens:
            if token not in seen:
                seen.add(token)
                result.append(token)
            for alias in ALIAS_MAP.get(token, []):
                if alias not in seen:
                    seen.add(alias)
                    result.append(alias)

        ctx.data.expanded_terms = result
        if self.config.debug:
            expansions = {}
            for token in tokens:
                if token in ALIAS_MAP and ALIAS_MAP[token]:
                    expansions[token] = ALIAS_MAP[token]
            ctx.data.debug["alias_expansions"] = expansions if expansions else {}
