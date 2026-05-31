"""Medical chat CLI — agentic consultation REPL."""
from __future__ import annotations

import asyncio
import logging
import os
import sys
from datetime import datetime, date as _date, UTC
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import typer
import aiosqlite

from src.chat.agentic_loop import AgenticLoopRunner
from src.chat.baseline_retriever import BaselineRetriever
from src.chat.config import ChatConfig
from src.chat.context_builder import _find_window_start
from src.chat.summarizer import summarize
from src.chat.tool_executor import KBToolExecutor
from src.common.logging_config import setup_logging
from src.common.patient import PatientInfo
from src.common.utils.parsers import load_categories
from src.llm.config import LLMConfig
from src.llm.mock import MockLLMClient
from src.llm.openai_client import OpenAICompatibleClient
from src.llm.retry_client import RetryLLMClient, RetryConfig
from src.pipelines.retrieval.config import RetrievalConfig
from src.pipelines.retrieval.runner import RetrievalRunner
from src.store.knowledge_store import DocSummary
from src.store.models import SessionRecord
from src.store.sql.sqlite_knowledge_store import SqliteKnowledgeStore
from src.store.sql.sqlite_internal_store import SqliteInternalStore

app = typer.Typer(add_completion=False)

_QUIT_COMMANDS = {"quit", "exit", "q"}

logger = logging.getLogger(__name__)


async def _init_schema(db_path: str | Path) -> None:
    """Initialize database schema from schema.sql."""
    schema = (Path(__file__).parent.parent / "store" / "sql" / "schema.sql").read_text()
    async with aiosqlite.connect(db_path) as conn:
        await conn.executescript(schema)


def _format_list(items: list[str]) -> str:
    """Format a list of strings for inline display in the system prompt."""
    return ", ".join(items) if items else "None"


def _format_document_index(docs: list[DocSummary]) -> str:
    """Format a list of DocSummary as a labeled table for the system prompt index.

    Returns the table rows only (header + data) — the section heading is in the
    system prompt template, not here.
    """
    if not docs:
        return "(no documents in knowledge base)"
    lines = ["document_id | date | category | sections"]
    for doc in docs:
        sections = ", ".join(doc.top_sections) if doc.top_sections else "—"
        lines.append(f"{doc.document_id} | {doc.document_date} | {doc.category} | {sections}")
    return "\n".join(lines)


def _build_system_message(
    template: str, patient: PatientInfo, now_date: str, document_index: str = ""
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


def _build_user_message(template: str, user_request: str, top_chunks: list[str], kb_excerpts: list[str]) -> str:
    top_text = "\n\n".join(top_chunks) if top_chunks else "No relevant excerpts found."
    extra_text = "\n\n".join(kb_excerpts) if kb_excerpts else "No additional evidence."
    return template.format(
        user_request=user_request,
        top_chunks=top_text,
        kb_excerpts=extra_text,
    )


def _log_context_stats(
        runner: AgenticLoopRunner, system_message: str, window_turns: int
) -> None:
    history = runner.history
    user_count = sum(1 for m in history if m.role == "user")
    assistant_count = sum(1 for m in history if m.role == "assistant")
    tool_count = sum(1 for m in history if m.role == "tool")
    window_start = _find_window_start(history, window_turns)
    windowed = history[window_start:]
    system_chars = len(system_message)
    summary_chars = len(runner.summary) if runner.summary else 0
    windowed_chars = sum(len(m.content or "") for m in windowed)
    total_chars = system_chars + summary_chars + windowed_chars
    logger.debug(
        "Context stats: history=%d (user=%d, asst=%d, tool=%d) | "
        "window=%d msgs | system=~%d chars | summary=%s (~%d chars) | "
        "windowed=~%d chars | total~%d chars / ~%d tokens (est.) | cursor=%d",
        len(history), user_count, assistant_count, tool_count,
        len(windowed), system_chars,
        "yes" if runner.summary else "no", summary_chars,
        windowed_chars, total_chars, total_chars // 4,
        runner.compressed_cursor,
    )


async def _try_compress_session(
        runner,
        chat_config: ChatConfig,
        llm_client,
        internal_store,
        session_id: str,
) -> None:
    """Check if compression should trigger and update session summary.

    Triggered after each turn: if user_count is a multiple of summarize_after_turns,
    compress the delta (history[compressed_cursor:window_start]) into a rolling summary.
    Compression is skipped when the delta is empty — this is expected until total turns
    exceed window_turns, after which messages start falling out of the window.

    Args:
        runner: AgenticLoopRunner instance.
        chat_config: Chat configuration.
        llm_client: LLM client for summarization.
        internal_store: Store for persisting session.
        session_id: Current session ID.
    """
    turns_count = sum(1 for m in runner.history if m.role == "user")
    if turns_count == 0 or turns_count % chat_config.memory.summarize_after_turns != 0:
        return

    history = runner.history
    window_start = _find_window_start(history, chat_config.memory.window_turns)
    messages_to_compress = history[runner.compressed_cursor:window_start]
    if not messages_to_compress:
        return

    try:
        new_summary = await summarize(llm_client, runner.summary, messages_to_compress)
        session = await internal_store.get_session(session_id)
        if session:
            session.summary = new_summary
            session.updated_at = datetime.now(UTC).isoformat()
            await internal_store.upsert_session(session)
        runner.summary = new_summary
        runner.mark_compressed(window_start)
    except Exception:
        logger.warning("Context compression failed, continuing without update", exc_info=True)


async def _chat_loop(
    runner: AgenticLoopRunner,
    retriever: BaselineRetriever,
    user_template: str,
        internal_store: SqliteInternalStore,
        session_id: str,
        llm_client,
        chat_config: ChatConfig,
        system_message: str,
        do_first_turn_retrieval: bool = True,
) -> None:
    """Run the interactive REPL until EOF or quit command.

    Baseline KB retrieval is performed only on the first turn when do_first_turn_retrieval
    is True and the patient describes their complaint. This is True for new sessions but
    False for resumed sessions (where history is already loaded). Subsequent turns (answers
    to the model's follow-up questions) are passed directly to AgenticLoopRunner — the LLM
    issues kb.search_chunks tool calls itself if it needs more context.

    After each turn, unsaved messages are persisted to the store and the save
    cursor is advanced. Context compression may trigger if the turn count reaches
    the summarize_after_turns threshold.

    Args:
        do_first_turn_retrieval: If True, perform baseline retrieval on first user input.
                                 If False (for resumed sessions), pass input directly.
    """
    print("Medical consultation started. Type your complaint and press Enter.")
    print("Type 'quit' or press Ctrl+D to exit.\n")

    while True:
        try:
            user_input = input("> ").strip()
        except EOFError:
            print("\nSession ended.")
            break

        if not user_input:
            continue
        if user_input.lower() in _QUIT_COMMANDS:
            print("Session ended.")
            break

        if do_first_turn_retrieval:
            bundle = await retriever.run(user_input)
            user_message = _build_user_message(user_template, user_input, bundle.top_chunks, bundle.kb_excerpts)
            do_first_turn_retrieval = False
        else:
            user_message = user_input

        response = await runner.run(user_message)

        # Save new messages after each turn
        unsaved = runner.unsaved_messages
        if unsaved:
            await internal_store.save_messages(session_id, runner.history)
            runner.mark_saved()

        # Attempt context compression if threshold reached
        await _try_compress_session(runner, chat_config, llm_client, internal_store, session_id)

        # Update session timestamp
        session = await internal_store.get_session(session_id)
        if session:
            session.updated_at = datetime.now(UTC).isoformat()
            await internal_store.upsert_session(session)

        print(f"\n{response}\n")

        _log_context_stats(runner, system_message, chat_config.memory.window_turns)


async def _list_sessions(internal_store: SqliteInternalStore) -> str | None:
    """Display all sessions and let user choose one or create new."""
    sessions = await internal_store.list_sessions(include_archived=False)

    if not sessions:
        print("No sessions found.")
        return None

    print("\nAvailable sessions:")
    for i, sess in enumerate(sessions, start=1):
        status_marker = "[P]" if sess.status == "pinned" else "    "
        print(f"{status_marker} {i}. {sess.title} ({sess.updated_at[:10]})")

    try:
        choice = input("\nSelect session (number) or 'n' for new: ").strip()
        if choice.lower() == "n":
            return None
        idx = int(choice) - 1
        if 0 <= idx < len(sessions):
            return sessions[idx].session_id
    except (ValueError, IndexError):
        pass
    return None


async def _create_session(internal_store: SqliteInternalStore, first_message: str) -> str:
    """Create a new session with auto-generated title from first message."""
    session_id = str(uuid4())
    now = datetime.now(UTC).isoformat()
    # Auto-title: first 50 chars of the user's first message
    auto_title = first_message[:50] if first_message else "New session"

    session = SessionRecord(
        session_id=session_id,
        title=auto_title,
        status="active",
        created_at=now,
        updated_at=now,
        summary=None,
    )
    await internal_store.upsert_session(session)
    return session_id


@app.command()
def chat(
    config_path: Path = typer.Option(Path("config/chat.yaml"), "--config"),  # noqa: B008
        session_id: str | None = typer.Option(None, "--session", help="Session ID to resume"),  # noqa: B008
    env: str = typer.Option("prod", "--env", help="prod | test"),  # noqa: B008
    debug: bool = typer.Option(False, "--debug", help="Enable DEBUG-level logging (all loggers, including libraries)."),  # noqa: B008
    pkg_debug: bool = typer.Option(False, "--pkg-debug", help="Enable DEBUG-level logging for project packages only."),  # noqa: B008
    log_file: Path | None = typer.Option(None, "--log-file", help="Write logs to file."),  # noqa: B008
) -> None:
    """Agentic medical consultation: interactive REPL with KB tool access."""
    setup_logging(
        level=logging.DEBUG if debug else logging.INFO,
        log_file=str(log_file) if log_file else None,
        debug_packages=pkg_debug,
    )

    chat_config = ChatConfig.load(config_path)
    retrieval_config = RetrievalConfig.load(Path("config/retrieve.yaml"))
    llm_config = LLMConfig.load(Path("config/llm.yaml"))
    patient = PatientInfo.load(Path("config/patient.yaml"))

    db_path = os.getenv("DB_PATH", ".data/db/ingest.db")
    asyncio.run(_init_schema(db_path))
    store = SqliteKnowledgeStore(db_path=db_path)
    internal_store = SqliteInternalStore(db_path=db_path)
    retrieval_runner = RetrievalRunner(store=store, config=retrieval_config)

    allowed_categories = frozenset(load_categories(Path("config/categories.yaml")))
    tool_executor = KBToolExecutor(
        retrieval_runner=retrieval_runner,
        retrieval_config=retrieval_config,
        allowed_categories=allowed_categories,
        max_search_chunks=chat_config.agentic_loop.max_search_chunks,
        max_search_chars=chat_config.agentic_loop.max_search_chars,
        max_get_document_chars=chat_config.agentic_loop.max_get_document_chars,
        max_tool_calls_per_turn=chat_config.agentic_loop.max_tool_calls_per_turn,
        store=store,
    )

    if env == "test":
        llm_client: MockLLMClient | OpenAICompatibleClient | RetryLLMClient = MockLLMClient()
    else:
        base_client = OpenAICompatibleClient(config=llm_config)
        # Wrap with retry logic if enabled in config
        if llm_config.retry_timeout_errors:
            retry_config = RetryConfig(
                max_retries=llm_config.retry_timeout_max_attempts - 1,
                initial_delay_sec=llm_config.retry_timeout_initial_delay,
                max_delay_sec=llm_config.retry_timeout_max_delay,
                backoff_factor=llm_config.retry_timeout_backoff_factor,
            )
            llm_client = RetryLLMClient(base_client, retry_config)
        else:
            llm_client = base_client

    system_template = Path("prompts/chat/system.md").read_text(encoding="utf-8")
    user_template = Path("prompts/chat/user.md").read_text(encoding="utf-8")
    now_date = _date.today().isoformat()
    all_docs = asyncio.run(store.list_docs(limit=200))
    document_index = _format_document_index(all_docs)
    system_message = _build_system_message(system_template, patient, now_date, document_index)

    # Session management
    history = None

    if session_id:
        # Resume existing session
        session_rec = asyncio.run(internal_store.get_session(session_id))
        if not session_rec:
            print(f"Session {session_id} not found.")
            sys.exit(1)
        print(f"Resuming session: [{session_rec.session_id}] {session_rec.title}")
        history = asyncio.run(internal_store.load_messages(session_id))
    else:
        # List sessions or create new
        session_id = asyncio.run(_list_sessions(internal_store))
        if session_id:
            print(f"Resuming session: [{session_id}]...")
            history = asyncio.run(internal_store.load_messages(session_id))
        else:
            print("Starting new session.")

    # Prepare to get session summary if resuming
    session_rec = None
    if session_id:
        session_rec = asyncio.run(internal_store.get_session(session_id))

    # When resuming, show the last assistant response so the user knows where the conversation left off
    if history:
        last_assistant = next(
            (m for m in reversed(history) if m.role == "assistant" and m.content),
            None,
        )
        if last_assistant:
            print(f"\n[Last response]\n\n{last_assistant.content}\n")

    agentic_runner = AgenticLoopRunner(
        llm_client=llm_client,
        tool_executor=tool_executor,
        system_message=system_message,
        loop_config=chat_config,
        history=history,
        summary=session_rec.summary if session_rec else None,
    )
    retriever = BaselineRetriever(
        retrieval_runner=retrieval_runner,
        store=store,
        retrieval_config=retrieval_config,
        chat_config=chat_config,
    )

    # If new session, create it
    if not session_id:
        # Peek at first user input to get title
        print("Medical consultation started. Type your complaint and press Enter.")
        print("Type 'quit' or press Ctrl+D to exit.\n")
        try:
            first_input = input("> ").strip()
        except EOFError:
            print("\nSession ended.")
            return

        if not first_input or first_input.lower() in _QUIT_COMMANDS:
            print("Session ended.")
            return

        session_id = asyncio.run(_create_session(internal_store, first_input))

        # Now run the loop with the first message already provided
        bundle = asyncio.run(retriever.run(first_input))
        user_message = _build_user_message(user_template, first_input, bundle.top_chunks, bundle.kb_excerpts)
        response = asyncio.run(agentic_runner.run(user_message))
        print(f"\n{response}\n")

        # Save after first turn
        unsaved = agentic_runner.unsaved_messages
        if unsaved:
            asyncio.run(internal_store.save_messages(session_id, agentic_runner.history))
            agentic_runner.mark_saved()
            session_rec = asyncio.run(internal_store.get_session(session_id))
            if session_rec:
                session_rec.updated_at = datetime.now(UTC).isoformat()
                asyncio.run(internal_store.upsert_session(session_rec))

        # Attempt context compression after first turn
        asyncio.run(_try_compress_session(agentic_runner, chat_config, llm_client, internal_store, session_id))
        _log_context_stats(agentic_runner, system_message, chat_config.memory.window_turns)

        # Continue with remaining turns
        asyncio.run(
            _chat_loop(
                agentic_runner,
                retriever,
                user_template,
                internal_store,
                session_id,
                llm_client,
                chat_config,
                system_message=system_message,
                do_first_turn_retrieval=False,  # History already started in first_input
            )
        )
    else:
        # Resume session: go straight to loop without first-turn retrieval
        # (history already loaded, so don't perform baseline retrieval)
        asyncio.run(
            _chat_loop(
                agentic_runner,
                retriever,
                user_template,
                internal_store,
                session_id,
                llm_client,
                chat_config,
                system_message=system_message,
                do_first_turn_retrieval=False,
            )
        )


if __name__ == "__main__":
    app()