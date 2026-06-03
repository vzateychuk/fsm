"""Application factory — builds the full AppContext from configuration files.

The factory is the single point of initialization for all stores, clients,
and application services. It is called once during FastAPI lifespan startup
and stores the result in app.state.ctx.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path

import aiosqlite

from src.api.config import ApiConfig
from src.chat.baseline_retriever import BaselineRetriever
from src.chat.config import ChatConfig
from src.chat.tool_executor import KBToolExecutor
from src.common.patient import PatientInfo
from src.common.utils.parsers import load_categories
from src.fsm.core import SagaDefinition
from src.fsm.saga_runner import SagaRunner
from src.llm.config import LLMConfig
from src.llm.openai_client import OpenAICompatibleClient
from src.llm.retry_client import RetryConfig, RetryLLMClient
from src.pipelines.ingest.config import IngestConfig
from src.pipelines.ingest.models import IngestData, IngestInput
from src.pipelines.ingest.steps import (
    BuildSectionPath,
    ChunkifyBlocks,
    DetectTargetSchema,
    LoadSource,
    ParseToTokens,
    PersistChunks,
    PersistDocument,
    PersistSourceFile,
    PreprocessText,
    SplitControlBlocks,
    Tagging,
)
from src.pipelines.retrieval.config import RetrievalConfig
from src.pipelines.retrieval.runner import RetrievalRunner
from src.services.chat import ChatService
from src.services.ingest import IngestService
from src.services.profile import ProfileService
from src.services.sessions import SessionsService
from src.store.file.local_file_store import LocalFileStore
from src.store.sql.sql_store import SqlStore
from src.store.sql.sqlite_internal_store import SqliteInternalStore
from src.store.sql.sqlite_knowledge_store import SqliteKnowledgeStore

logger = logging.getLogger(__name__)


@dataclass
class AppContext:
    """Container for all initialized application services."""

    sessions_service: SessionsService
    profile_service: ProfileService
    ingest_service: IngestService
    chat_service: ChatService
    api_config: ApiConfig


async def ensure_schema(db_path: str) -> None:
    """Initialize the database schema (idempotent; safe to call on every startup)."""
    schema_path = Path(__file__).parent.parent / "store" / "sql" / "schema.sql"
    schema = schema_path.read_text(encoding="utf-8")
    async with aiosqlite.connect(db_path) as conn:
        await conn.executescript(schema)
    logger.info("Schema initialized: db=%s", db_path)


async def create_app_context(
    api_config_path: Path = Path("config/api.yaml"),
) -> AppContext:
    """Build the full application context.

    Reads all config files, initializes stores, LLM client, and all
    application services. Calls ensure_schema to make sure the DB is ready.

    Args:
        api_config_path: Path to config/api.yaml.

    Returns:
        AppContext with all services wired up.
    """
    api_config = ApiConfig.load(api_config_path)
    llm_config = LLMConfig.load(Path("config/llm.yaml"))
    chat_config = ChatConfig.load(Path("config/chat.yaml"))
    retrieval_config = RetrievalConfig.load(Path("config/retrieve.yaml"))
    ingest_config = IngestConfig.load(Path("config/ingest.yaml"))
    patient = PatientInfo.load(Path("config/patient.yaml"))

    db_path = os.getenv("DB_PATH", ".data/db/ingest.db")
    filestore_dir = os.getenv("FILESTORE_DIR", ".data/filestore")

    # Ensure the DB directory exists before connecting
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    await ensure_schema(db_path)

    knowledge_store = SqliteKnowledgeStore(db_path=db_path)
    internal_store = SqliteInternalStore(db_path=db_path)
    saga_store = SqlStore(db_path=db_path)
    file_store = LocalFileStore(filestore_dir=filestore_dir)

    # LLM client with optional retry wrapper
    base_client = OpenAICompatibleClient(config=llm_config)
    if llm_config.retry_timeout_errors:
        retry_config = RetryConfig(
            max_retries=llm_config.retry_timeout_max_attempts - 1,
            initial_delay_sec=llm_config.retry_timeout_initial_delay,
            max_delay_sec=llm_config.retry_timeout_max_delay,
            backoff_factor=llm_config.retry_timeout_backoff_factor,
        )
        llm_client: OpenAICompatibleClient | RetryLLMClient = RetryLLMClient(
            base_client, retry_config
        )
    else:
        llm_client = base_client

    retrieval_runner = RetrievalRunner(store=knowledge_store, config=retrieval_config)

    allowed_categories = frozenset(load_categories(Path("config/categories.yaml")))
    tool_executor = KBToolExecutor(
        retrieval_runner=retrieval_runner,
        retrieval_config=retrieval_config,
        allowed_categories=allowed_categories,
        max_search_chunks=chat_config.agentic_loop.max_search_chunks,
        max_search_chars=chat_config.agentic_loop.max_search_chars,
        max_get_document_chars=chat_config.agentic_loop.max_get_document_chars,
        max_tool_calls_per_turn=chat_config.agentic_loop.max_tool_calls_per_turn,
        store=knowledge_store,
    )

    retriever = BaselineRetriever(
        retrieval_runner=retrieval_runner,
        store=knowledge_store,
        retrieval_config=retrieval_config,
        chat_config=chat_config,
    )

    system_template = Path("prompts/chat/system.md").read_text(encoding="utf-8")
    user_template = Path("prompts/chat/user.md").read_text(encoding="utf-8")

    # Build ingest saga runner
    categories_config = Path("config/categories.yaml")
    ingest_definition: SagaDefinition[IngestInput, IngestData] = SagaDefinition(
        name="ingest",
        steps=[
            LoadSource(),
            PreprocessText(),
            DetectTargetSchema(categories_config=categories_config),
            SplitControlBlocks(categories_config=categories_config),
            ParseToTokens(),
            BuildSectionPath(),
            ChunkifyBlocks(
                admin_headings=ingest_config.admin_section_headings,
                max_section_chars=ingest_config.max_section_chars,
            ),
            Tagging(),
            PersistSourceFile(store=file_store),
            PersistDocument(store=knowledge_store),
            PersistChunks(store=knowledge_store),
        ],
    )
    ingest_runner: SagaRunner[IngestInput, IngestData] = SagaRunner(
        ingest_definition, saga_store, IngestData
    )

    sessions_service = SessionsService(internal_store=internal_store)
    profile_service = ProfileService(patient=patient)
    ingest_service = IngestService(
        saga_runner=ingest_runner,
        knowledge_store=knowledge_store,
    )
    chat_service = ChatService(
        internal_store=internal_store,
        knowledge_store=knowledge_store,
        llm_client=llm_client,
        tool_executor=tool_executor,
        retriever=retriever,
        chat_config=chat_config,
        patient=patient,
        system_template=system_template,
        user_template=user_template,
    )

    logger.info("AppContext initialized (db=%s)", db_path)
    return AppContext(
        sessions_service=sessions_service,
        profile_service=profile_service,
        ingest_service=ingest_service,
        chat_service=chat_service,
        api_config=api_config,
    )
