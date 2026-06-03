"""ChatService — agentic consultation turns and message history."""
from __future__ import annotations

import logging
from datetime import date, datetime, UTC

from src.chat.agentic_loop import AgenticLoopRunner
from src.chat.baseline_retriever import BaselineRetriever
from src.chat.config import ChatConfig
from src.chat.context_builder import _find_window_start
from src.chat.summarizer import summarize
from src.chat.tool_executor import KBToolExecutor
from src.llm.errors import LLMError
from src.llm.llm_client import LLMClient
from src.store.internal_store import InternalStore
from src.store.knowledge_store import DocSummary, KnowledgeStore
from src.store.models import MessageRecord
from src.common.patient import PatientInfo
from src.services.errors import (
    AppError,
    NotFoundError,
    LLMTimeoutError,
    LLMUnavailableError,
    LLMRequestInvalidError,
)

logger = logging.getLogger(__name__)

_TIMEOUT_KEYWORDS = ("timed out", "timeout", "readtimeout")
_UNAVAILABLE_KEYWORDS = ("502", "503", "server error", "bad gateway", "service unavailable")


def _classify_llm_error(error: LLMError) -> AppError:
    """Map an LLMError to the appropriate domain exception."""
    msg = str(error).lower()
    if any(kw in msg for kw in _TIMEOUT_KEYWORDS):
        return LLMTimeoutError(str(error))
    if any(kw in msg for kw in _UNAVAILABLE_KEYWORDS):
        return LLMUnavailableError(str(error))
    return LLMRequestInvalidError(str(error))


def _format_list(items: list[str]) -> str:
    return ", ".join(items) if items else "None"


def _format_document_index(docs: list[DocSummary]) -> str:
    if not docs:
        return "(no documents in knowledge base)"
    lines = ["document_id | date | category | sections"]
    for doc in docs:
        sections = ", ".join(doc.top_sections) if doc.top_sections else "\u2014"
        lines.append(
            f"{doc.document_id} | {doc.document_date} | {doc.category} | {sections}"
        )
    return "\n".join(lines)


def _build_system_message(
    template: str,
    patient: PatientInfo,
    now_date: str,
    document_index: str,
) -> str:
    return template.format(
        age=patient.age,
        sex=patient.sex,
        chronic_conditions=_format_list(patient.chronic_conditions),
        current_medications=_format_list(patient.current_medications),
        allergies=_format_list(patient.allergies),
        now_date=now_date,
        document_index=document_index,
    )


def _build_user_message(
    template: str,
    user_request: str,
    top_chunks: list[str],
    kb_excerpts: list[str],
) -> str:
    top_text = "\n\n".join(top_chunks) if top_chunks else "No relevant excerpts found."
    extra_text = "\n\n".join(kb_excerpts) if kb_excerpts else "No additional evidence."
    return template.format(
        user_request=user_request,
        top_chunks=top_text,
        kb_excerpts=extra_text,
    )


class ChatService:
    """Application service for agentic medical consultation.

    Manages the full lifecycle of a chat turn:
    - Loading session history and summary from persistence
    - Optionally performing baseline KB retrieval on the first turn
    - Running the agentic loop (AgenticLoopRunner, recreated per request)
    - Persisting new messages after a successful turn
    - Triggering rolling summary compression when the threshold is reached
    """

    def __init__(
        self,
        internal_store: InternalStore,
        knowledge_store: KnowledgeStore,
        llm_client: LLMClient,
        tool_executor: KBToolExecutor,
        retriever: BaselineRetriever,
        chat_config: ChatConfig,
        patient: PatientInfo,
        system_template: str,
        user_template: str,
    ) -> None:
        self._internal_store = internal_store
        self._knowledge_store = knowledge_store
        self._llm = llm_client
        self._tool_executor = tool_executor
        self._retriever = retriever
        self._chat_config = chat_config
        self._patient = patient
        self._system_template = system_template
        self._user_template = user_template

    async def send_message(
        self,
        session_id: str,
        content: str,
    ) -> MessageRecord:
        """Send a user message and return the assistant response.

        Args:
            session_id: Session to send the message to.
            content: User's message text.

        Returns:
            MessageRecord for the assistant's response.

        Raises:
            NotFoundError: If the session does not exist.
            LLMTimeoutError: If the LLM times out after retries.
            LLMUnavailableError: If the LLM returns a 5xx error.
            LLMRequestInvalidError: If the LLM rejects the request.
        """
        session = await self._internal_store.get_session(session_id)
        if session is None:
            raise NotFoundError(f"Session {session_id!r} not found")

        history = await self._internal_store.load_messages(session_id)

        all_docs = await self._knowledge_store.list_docs(limit=200)
        document_index = _format_document_index(all_docs)
        now_date = date.today().isoformat()
        system_message = _build_system_message(
            self._system_template, self._patient, now_date, document_index
        )

        runner = AgenticLoopRunner(
            llm_client=self._llm,
            tool_executor=self._tool_executor,
            system_message=system_message,
            loop_config=self._chat_config,
            history=history,
            summary=session.summary,
        )

        # On the first turn, perform baseline KB retrieval to seed context.
        # On subsequent turns the LLM issues tool calls itself if needed.
        is_first_turn = len(history) == 0
        if is_first_turn:
            bundle = await self._retriever.run(content)
            user_message = _build_user_message(
                self._user_template,
                content,
                bundle.top_chunks,
                bundle.kb_excerpts,
            )
        else:
            user_message = content

        try:
            await runner.run(user_message)
        except LLMError as exc:
            raise _classify_llm_error(exc) from exc

        # Persist messages atomically after a successful turn.
        await self._internal_store.save_messages(session_id, runner.history)
        runner.mark_saved()

        session.updated_at = datetime.now(UTC).isoformat()
        await self._internal_store.upsert_session(session)

        await self._try_compress_session(runner, session_id)

        msg = await self._internal_store.get_last_assistant_message(session_id)
        if msg is None:
            # Defensive fallback: synthesise a record from the last history entry.
            last = runner.history[-1]
            msg = MessageRecord(
                message_id="",
                session_id=session_id,
                role="assistant",
                content=last.content or "",
                created_at=datetime.now(UTC).isoformat(),
            )

        logger.info(
            "Chat turn completed session=%s history_len=%d",
            session_id,
            len(runner.history),
        )
        return msg

    async def get_messages(
        self,
        session_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[MessageRecord]:
        """Return visible message history for a session.

        Args:
            session_id: Session identifier.
            limit: Maximum messages to return.
            offset: Messages to skip.

        Returns:
            List of MessageRecord (user and final assistant messages only).

        Raises:
            NotFoundError: If the session does not exist.
        """
        session = await self._internal_store.get_session(session_id)
        if session is None:
            raise NotFoundError(f"Session {session_id!r} not found")
        return await self._internal_store.list_session_messages(
            session_id, limit=limit, offset=offset
        )

    async def _try_compress_session(
        self,
        runner: AgenticLoopRunner,
        session_id: str,
    ) -> None:
        """Trigger rolling summary compression if the turn threshold is reached."""
        turns_count = sum(1 for m in runner.history if m.role == "user")
        if turns_count == 0 or turns_count % self._chat_config.memory.summarize_after_turns != 0:
            return

        history = runner.history
        window_start = _find_window_start(history, self._chat_config.memory.window_turns)
        messages_to_compress = history[runner.compressed_cursor:window_start]
        if not messages_to_compress:
            return

        try:
            new_summary = await summarize(self._llm, runner.summary, messages_to_compress)
            session = await self._internal_store.get_session(session_id)
            if session:
                session.summary = new_summary
                session.updated_at = datetime.now(UTC).isoformat()
                await self._internal_store.upsert_session(session)
            runner.summary = new_summary
            runner.mark_compressed(window_start)
            logger.info("Context compression applied session=%s", session_id)
        except Exception:
            logger.warning(
                "Context compression failed, continuing without update",
                exc_info=True,
            )
