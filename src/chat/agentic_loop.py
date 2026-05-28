"""AgenticLoopRunner — orchestrates the agentic chat consultation loop."""

import logging

from src.chat.config import ChatConfig
from src.chat.tool_executor import KBToolExecutor
from src.llm.llm_client import LLMClient
from src.llm.models import ChatRequest, ChatResponse, Message, ToolDefinition

logger = logging.getLogger(__name__)

# Tool definition sent to the LLM in every request.
# Description text is taken verbatim from spec section D.1.
# TODO: move to the config/property file
_KB_SEARCH_TOOL = ToolDefinition(
    name="kb.search_chunks",
    description=(
        "Search the patient's medical history in the knowledge base.\n"
        "Call this when the current context is insufficient to refine your differential diagnosis.\n"
        "Provide a focused query; optionally filter by category and date window."
    ),
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": (
                    "Search query text (symptoms, terms, indicators). "
                    "Example: 'лейкоциты нейтрофилы воспаление'"
                ),
            },
            "category": {
                "type": "string",
                "description": "Optional document type filter (e.g. Анализы, Диагноз, Консультация).",
            },
            "from_date": {
                "type": "string",
                "description": "Optional lower bound for document_date (YYYY-MM-DD).",
            },
            "to_date": {
                "type": "string",
                "description": "Optional upper bound for document_date (YYYY-MM-DD).",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of chunks to return.",
            },
        },
        "required": ["query", "limit"],
    },
)

# TODO : переместить в config
_KB_GET_DOCUMENT_TOOL = ToolDefinition(
    name="kb.get_document",
    description=(
        "Fetch all chunks from a specific document in the knowledge base.\n"
        "Use this when you know the document_id from the Medical Records Index and want\n"
        "to read its full content or specific sections.\n"
        "Prefer this over kb.search_chunks when you need complete context from a known document.\n"
        "Always call this when the user explicitly asks to show, find, read, or retrieve\n"
        "a document by its ID — even if some excerpts from that document are already in context."
    ),
    parameters={
        "type": "object",
        "properties": {
            "document_id": {
                "type": "string",
                "description": "Exact document identifier as listed in the Medical Records Index.",
            },
            "sections": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Optional list of top-level section names to filter (e.g. ['Общий анализ крови']). "
                    "If omitted, all sections are returned."
                ),
            },
        },
        "required": ["document_id"],
    },
)

_ROUNDTRIP_BUDGET_EXHAUSTED = (
    "Tool call rejected: KB roundtrip budget exhausted for this turn."
)


class AgenticLoopRunner:
    """Orchestrates the agentic LLM loop for a chat consultation session.

    Manages conversation history, tool execution via KBToolExecutor, and
    enforces the max_kb_roundtrips guardrail.

    One instance is created per chat session and reused across all patient turns.
    History accumulates across turns — the full conversation context is sent to
    the LLM on every call.

    Usage::

        runner = AgenticLoopRunner(llm_client, tool_executor, system_message, chat_config)
        response_text = await runner.run(user_message)
    """

    def __init__(
        self,
        llm_client: LLMClient,
        tool_executor: KBToolExecutor,
        system_message: str,
        loop_config: ChatConfig,
    ) -> None:
        self._llm = llm_client
        self._tool_executor = tool_executor
        self._system_message = system_message
        self._cfg = loop_config.agentic_loop
        self._history: list[Message] = []

    @property
    def history(self) -> list[Message]:
        """Read-only view of the current conversation history (excluding system message)."""
        return list(self._history)

    async def run(self, user_message: str) -> str:
        """Execute one patient turn: user message → agentic loop → final text.

        Adds the user message to history, runs the tool loop until the LLM
        returns a text-only response or the roundtrip budget is exhausted,
        and returns the final assistant text to be shown to the patient.

        Args:
            user_message: Patient's message (may include baseline KB excerpts on first turn).

        Returns:
            Final assistant response text.
        """
        self._history.append(Message(role="user", content=user_message))
        return await self._run_tool_loop()

    async def _run_tool_loop(self) -> str:
        """Inner loop: call LLM → handle tool_calls → repeat until text response."""
        roundtrips = 0

        while True:
            response = await self._call_llm(with_tools=True)

            if not response.tool_calls:
                # Final (or only) assistant turn — show to patient.
                self._history.append(Message(role="assistant", content=response.text))
                return response.text

            # Intermediate assistant turn with tool calls.
            # Content is logged for debugging but not shown to the patient.
            if response.text:
                logger.debug(
                    "Intermediate assistant turn (roundtrip=%d, tool_calls=%d): %.200s",
                    roundtrips,
                    len(response.tool_calls),
                    response.text,
                )

            self._history.append(
                Message(
                    role="assistant",
                    content=response.text,
                    tool_calls=response.tool_calls,
                )
            )

            logger.debug(
                "Assistant response: '%s' dispatched: roundtrip=%d tool_calls=%s",
                response.text,
                roundtrips,
                [tc.name for tc in response.tool_calls],
            )

            if roundtrips >= self._cfg.max_kb_roundtrips:
                # Budget exhausted: reject all tool calls with an error result,
                # then make a final call without tools so the LLM can summarise
                # based on whatever context it has accumulated.
                logger.info(
                    "KB roundtrip budget exhausted (max=%d), sending error results.",
                    self._cfg.max_kb_roundtrips,
                )
                for tc in response.tool_calls:
                    self._history.append(
                        Message(
                            role="tool",
                            content=_ROUNDTRIP_BUDGET_EXHAUSTED,
                            tool_call_id=tc.id,
                        )
                    )
                final = await self._call_llm(with_tools=False)
                self._history.append(Message(role="assistant", content=final.text))
                return final.text

            # Execute tool calls and record results in history.
            tool_results = await self._tool_executor.execute(response.tool_calls)
            for tr in tool_results:
                self._history.append(
                    Message(role="tool", content=tr.content, tool_call_id=tr.tool_call_id)
                )

            roundtrips += 1

    async def _call_llm(self, *, with_tools: bool) -> ChatResponse:
        """Build a request from system message + history and call the LLM.

        Args:
            with_tools: When True, includes the kb.search_chunks tool definition.
                        When False, sends a tools-free request (e.g. for final call
                        after budget exhaustion).
        """
        system_msg = Message(role="system", content=self._system_message)
        messages = [system_msg] + self._history
        tools = [_KB_SEARCH_TOOL, _KB_GET_DOCUMENT_TOOL] if with_tools else []
        return await self._llm.chat(ChatRequest(messages=messages, tools=tools))
