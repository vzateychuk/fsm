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
    """R3: Expand query terms via alias map with OR semantics.

    Each token from query_normalized is looked up in ALIAS_MAP. Original
    tokens and any aliases are collected in order, deduplicated, and stored
    in ctx.data.expanded_terms.
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
