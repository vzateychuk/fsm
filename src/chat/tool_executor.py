"""KBToolExecutor — executes kb.search_chunks tool calls for the agentic loop."""

import logging
import re

from src.llm.models import ToolCall, ToolResult
from src.pipelines.retrieval.config import RetrievalConfig
from src.pipelines.retrieval.models import RetrieveRequest
from src.pipelines.retrieval.runner import RetrievalRunner
from src.store.knowledge_store import ChunkSearchResult, KnowledgeStore

logger = logging.getLogger(__name__)

_ALLOWED_TOOL_NAMES = {"kb.search_chunks", "kb.get_document"}

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class KBToolExecutor:
    """Executes kb.search_chunks tool calls and returns formatted results.

    Enforces per-turn limits, tool name allowlist, category allowlist,
    date format/range validation, limit cap, and char budget on output.

    allowed_categories must be loaded externally (e.g. via load_categories()
    from src.common.utils.parsers) and passed at construction time.
    """

    def __init__(
        self,
        retrieval_runner: RetrievalRunner,
        retrieval_config: RetrievalConfig,
        allowed_categories: frozenset[str],
        max_search_chunks: int,
        max_search_chars: int,
        max_get_document_chars: int,
        max_tool_calls_per_turn: int,
        store: KnowledgeStore,
    ) -> None:
        self._runner = retrieval_runner
        self._retrieval_config = retrieval_config
        self._allowed_categories = allowed_categories
        self._max_search_chunks = max_search_chunks
        self._max_search_chars = max_search_chars
        self._max_get_document_chars = max_get_document_chars
        self._max_tool_calls_per_turn = max_tool_calls_per_turn
        self._store = store

    async def execute(self, tool_calls: list[ToolCall]) -> list[ToolResult]:
        """Execute all tool calls for one assistant turn.

        Calls beyond max_tool_calls_per_turn receive an error result without
        executing. Returns one ToolResult per input ToolCall, in order.
        """
        results: list[ToolResult] = []
        for i, tc in enumerate(tool_calls):
            if i >= self._max_tool_calls_per_turn:
                content = "Tool call rejected: tool call budget exhausted for this turn."
            else:
                content = await self._dispatch(tc)
            results.append(ToolResult(tool_call_id=tc.id, content=content))
        return results

    async def _dispatch(self, tc: ToolCall) -> str:
        if tc.name not in _ALLOWED_TOOL_NAMES:
            allowed = ", ".join(sorted(_ALLOWED_TOOL_NAMES))
            return f"Tool '{tc.name}' is not allowed. Allowed tools: {allowed}."
        if tc.name == "kb.get_document":
            return await self._execute_kb_get_document(tc)
        return await self._execute_kb_search(tc)

    async def _execute_kb_search(self, tc: ToolCall) -> str:
        args = tc.arguments

        query: str | None = args.get("query")
        if not query or not isinstance(query, str):
            return 'Missing required argument: "query".'

        limit = args.get("limit")
        if limit is None:
            return 'Missing required argument: "limit".'
        if not isinstance(limit, int) or limit <= 0:
            return 'Argument "limit" must be a positive integer.'

        category: str | None = args.get("category")
        if category is not None and category not in self._allowed_categories:
            allowed = ", ".join(sorted(self._allowed_categories))
            return f'Invalid category: "{category}". Allowed values: {allowed}.'

        from_date: str | None = args.get("from_date")
        to_date: str | None = args.get("to_date")
        if from_date is not None and not _DATE_RE.match(from_date):
            return "Invalid date format, expected YYYY-MM-DD."
        if to_date is not None and not _DATE_RE.match(to_date):
            return "Invalid date format, expected YYYY-MM-DD."
        if from_date is not None and to_date is not None and from_date > to_date:
            return "Invalid date range: from_date must be <= to_date."

        capped_limit = min(limit, self._max_search_chunks)
        logger.info(
            "kb.search_chunks: query=%r category=%r from=%s to=%s limit=%d",
            query,
            category,
            from_date or "-",
            to_date or "-",
            capped_limit,
        )
        request = RetrieveRequest(
            query=query,
            category=category,
            from_date=from_date,
            to_date=to_date,
            limit=capped_limit,
            limit_per_document=self._retrieval_config.query_limit_per_document,
            prelimit=self._retrieval_config.prelimit,
        )

        response = await self._runner.run(request)
        chunk_refs = [
            f"{c.document_id}#chunk_{c.chunk_no} | {c.document_date} | {c.category} | {c.section_path or ''}"
            for c in response.chunks
        ]
        logger.debug("kb.search_chunks: returned %d chunks\n: %s", len(chunk_refs), "\n  ".join(chunk_refs))

        if not response.chunks:
            return f'No matches found for query: "{query}"'

        return self._format_tool_result(response.chunks, query, self._max_search_chars)

    async def _execute_kb_get_document(self, tc: ToolCall) -> str:
        args = tc.arguments

        document_id: str | None = args.get("document_id")
        if not document_id or not isinstance(document_id, str):
            return 'Missing required argument: "document_id".'

        sections: list[str] | None = args.get("sections")
        if sections is not None and not isinstance(sections, list):
            return 'Argument "sections" must be a list of strings.'

        logger.info("kb.get_document: document_id=%r sections=%r", document_id, sections)

        chunks = await self._store.get_document_chunks(document_id, limit=200)
        if not chunks:
            return f'No document found with id: "{document_id}"'

        if sections:
            section_set = {s.strip().lower() for s in sections}
            chunks = [
                c
                for c in chunks
                if c.section_path and c.section_path.split(" > ")[0].strip().lower() in section_set
            ]
            if not chunks:
                return (
                    f'No chunks found in document "{document_id}" '
                    f'matching sections: {sections}.'
                )

        chunk_refs = [
            f"{c.document_id}#chunk_{c.chunk_no} | {c.document_date} | {c.category} | {c.section_path or ''}"
            for c in chunks
        ]
        logger.debug("kb.get_document: returned %d chunks\n  %s", len(chunk_refs), "\n  ".join(chunk_refs))

        return self._format_tool_result(chunks, document_id, self._max_get_document_chars)

    def _format_tool_result(self, chunks: list[ChunkSearchResult], query: str, char_budget: int | None = None) -> str:
        """Format chunks as structured tool result text within char budget.

        First chunk (highest rank) goes into ## Top Matches.
        Remaining chunks that fit within budget go into ## Additional Matches.
        The last chunk to be included is truncated with '[truncated]' if it
        does not fit entirely within the remaining budget.
        char_budget defaults to self._max_search_chars when not provided.
        """
        budget = char_budget if char_budget is not None else self._max_search_chars
        top: list[str] = []
        additional: list[str] = []
        total_chars = 0

        for i, chunk in enumerate(chunks):
            section = chunk.section_path or ""
            header = (
                f"{chunk.document_id}#chunk_{chunk.chunk_no}"
                f" | {chunk.document_date} | {chunk.category} | {section}"
            )
            excerpt = f"{header}\n\n{chunk.text}"
            remaining = budget - total_chars

            if remaining <= 0:
                break

            if len(excerpt) <= remaining:
                bucket = top if i == 0 else additional
                bucket.append(excerpt)
                total_chars += len(excerpt)
            else:
                truncate_at = max(0, remaining - len("[truncated]"))
                truncated = excerpt[:truncate_at] + "[truncated]"
                bucket = top if i == 0 else additional
                bucket.append(truncated)
                break

        if not top:
            return f'No matches found for query: "{query}"'

        sections: list[str] = ["## Top Matches", "", "\n\n".join(top)]
        if additional:
            sections += ["", "## Additional Matches", "", "\n\n".join(additional)]

        return "\n".join(sections)
