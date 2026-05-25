"""KBToolExecutor — executes kb.search_chunks tool calls for the agentic loop."""

import re

from src.llm.models import ToolCall, ToolResult
from src.pipelines.retrieval.config import RetrievalConfig
from src.pipelines.retrieval.models import RetrieveRequest
from src.pipelines.retrieval.runner import RetrievalRunner
from src.store.knowledge_store import ChunkSearchResult

_ALLOWED_TOOL_NAME = "kb.search_chunks"

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
        max_tool_chunks: int,
        max_tool_total_chars: int,
        max_tool_calls_per_turn: int,
    ) -> None:
        self._runner = retrieval_runner
        self._retrieval_config = retrieval_config
        self._allowed_categories = allowed_categories
        self._max_tool_chunks = max_tool_chunks
        self._max_tool_total_chars = max_tool_total_chars
        self._max_tool_calls_per_turn = max_tool_calls_per_turn

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
        if tc.name != _ALLOWED_TOOL_NAME:
            return (
                f"Tool '{tc.name}' is not allowed. "
                f"Only '{_ALLOWED_TOOL_NAME}' is permitted."
            )
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

        capped_limit = min(limit, self._max_tool_chunks)
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

        if not response.chunks:
            return f'No matches found for query: "{query}"'

        return self._format_tool_result(response.chunks, query)

    def _format_tool_result(self, chunks: list[ChunkSearchResult], query: str) -> str:
        """Format chunks as structured tool result text within char budget.

        Iterates chunks in rank order. Stops when max_tool_total_chars is reached.
        The last chunk to be included is truncated with '[truncated]' if it
        does not fit entirely within the remaining budget.
        """
        parts: list[str] = []
        total_chars = 0

        for chunk in chunks:
            section = chunk.section_path or ""
            header = (
                f"{chunk.document_id}#chunk_{chunk.chunk_no}"
                f" | {chunk.document_date} | {chunk.category} | {section}"
            )
            excerpt = f"{header}\n\n{chunk.text}"
            remaining = self._max_tool_total_chars - total_chars

            if remaining <= 0:
                break

            if len(excerpt) <= remaining:
                parts.append(excerpt)
                total_chars += len(excerpt)
            else:
                truncate_at = max(0, remaining - len("[truncated]"))
                parts.append(excerpt[:truncate_at] + "[truncated]")
                break

        if not parts:
            return f'No matches found for query: "{query}"'

        return "## Top Matches\n\n" + "\n\n".join(parts)
