"""Medical chat CLI — agentic consultation REPL."""
from __future__ import annotations

import asyncio
import logging
import os
import sys
from datetime import UTC, datetime, date as _date
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parent.parent.parent))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import typer
import aiosqlite

from src.chat.agentic_loop import AgenticLoopRunner
from src.chat.baseline_retriever import BaselineRetriever
from src.chat.config import ChatConfig
from src.chat.tool_executor import KBToolExecutor
from src.common.logging_config import setup_logging
from src.common.patient import PatientInfo
from src.common.utils.parsers import load_categories
from src.llm.config import LLMConfig
from src.llm.mock import MockLLMClient
from src.llm.openai_client import OpenAICompatibleClient
from src.pipelines.retrieval.config import RetrievalConfig
from src.pipelines.retrieval.runner import RetrievalRunner
from src.store.knowledge_store import DocSummary
from src.store.sql.sqlite_knowledge_store import SqliteKnowledgeStore

app = typer.Typer(add_completion=False)

_QUIT_COMMANDS = {"quit", "exit", "q"}


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


async def _chat_loop(
    runner: AgenticLoopRunner,
    retriever: BaselineRetriever,
    user_template: str,
) -> None:
    """Run the interactive REPL until EOF or quit command.

    Baseline KB retrieval is performed only on the first turn, when the patient
    describes their complaint. Subsequent turns (answers to the model's follow-up
    questions) are passed directly to AgenticLoopRunner — the LLM issues
    kb.search_chunks tool calls itself if it needs more context.
    """
    print("Medical consultation started. Type your complaint and press Enter.")
    print("Type 'quit' or press Ctrl+D to exit.\n")

    first_turn = True

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

        if first_turn:
            bundle = await retriever.run(user_input)
            user_message = _build_user_message(user_template, user_input, bundle.top_chunks, bundle.kb_excerpts)
            first_turn = False
        else:
            user_message = user_input

        response = await runner.run(user_message)
        print(f"\n{response}\n")


@app.command()
def chat(
    config_path: Path = typer.Option(Path("config/chat.yaml"), "--config"),  # noqa: B008
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
    store = SqliteKnowledgeStore(db_path=db_path)
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
        llm_client: MockLLMClient | OpenAICompatibleClient = MockLLMClient()
    else:
        llm_client = OpenAICompatibleClient(config=llm_config)

    system_template = Path("prompts/chat/system.md").read_text(encoding="utf-8")
    user_template = Path("prompts/chat/user.md").read_text(encoding="utf-8")
    now_date = _date.today().isoformat()
    all_docs = asyncio.run(store.list_docs(limit=200))
    document_index = _format_document_index(all_docs)
    system_message = _build_system_message(system_template, patient, now_date, document_index)

    agentic_runner = AgenticLoopRunner(
        llm_client=llm_client,
        tool_executor=tool_executor,
        system_message=system_message,
        loop_config=chat_config,
    )
    retriever = BaselineRetriever(
        retrieval_runner=retrieval_runner,
        store=store,
        retrieval_config=retrieval_config,
        chat_config=chat_config,
    )

    asyncio.run(_chat_loop(agentic_runner, retriever, user_template))


if __name__ == "__main__":
    app()
