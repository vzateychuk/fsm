"""Per-user application context and factory."""

from __future__ import annotations

import logging
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path

from src.api.config import ApiConfig
from src.chat.baseline_retriever import BaselineRetriever
from src.chat.config import ChatConfig
from src.chat.tool_executor import KBToolExecutor
from src.common.utils.parsers import load_categories
from src.fsm.core import SagaDefinition
from src.fsm.saga_runner import SagaRunner
from src.llm.llm_client import LLMClient
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
    PreprocessText,
    SplitControlBlocks,
    Tagging,
)
from src.pipelines.retrieval.config import RetrievalConfig
from src.pipelines.retrieval.runner import RetrievalRunner
from src.services.chat import ChatService
from src.services.documents import DocumentsService
from src.services.ingest import IngestService
from src.services.profile import ProfileService
from src.services.sessions import SessionsService
from src.store.sql.sql_store import SqlStore
from src.store.sql.sqlite_internal_store import SqliteInternalStore
from src.store.sql.sqlite_knowledge_store import SqliteKnowledgeStore
logger = logging.getLogger(__name__)


@dataclass
class UserContext:
    """All services scoped to one user's database."""

    username: str
    db_path: str
    sessions_service: SessionsService
    profile_service: ProfileService
    ingest_service: IngestService
    documents_service: DocumentsService
    chat_service: ChatService


@dataclass
class SharedContext:
    """Process-wide resources shared across users."""

    api_config: ApiConfig
    auth_service: object  # AuthService — avoid circular import in type hints
    user_factory: UserContextFactory


class UserContextFactory:
    """Build and cache UserContext instances per (username, db_path)."""

    def __init__(
        self,
        *,
        llm_client: LLMClient,
        chat_config: ChatConfig,
        retrieval_config: RetrievalConfig,
        ingest_config: IngestConfig,
        system_template: str,
        user_template: str,
        max_cache_size: int = 32,
    ) -> None:
        self._llm_client = llm_client
        self._chat_config = chat_config
        self._retrieval_config = retrieval_config
        self._ingest_config = ingest_config
        self._system_template = system_template
        self._user_template = user_template
        self._cache: OrderedDict[tuple[str, str], UserContext] = OrderedDict()
        self._max_cache_size = max_cache_size

    async def get(self, username: str, db_path: str) -> UserContext:
        key = (username, db_path)
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]

        from src.api.schema_init import ensure_schema  # noqa: PLC0415

        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        await ensure_schema(db_path)

        ctx = self._build(username, db_path)
        self._cache[key] = ctx
        if len(self._cache) > self._max_cache_size:
            self._cache.popitem(last=False)
        logger.debug("UserContext created username=%s db=%s", username, db_path)
        return ctx

    def _build(self, username: str, db_path: str) -> UserContext:
        knowledge_store = SqliteKnowledgeStore(db_path=db_path)
        internal_store = SqliteInternalStore(db_path=db_path)
        saga_store = SqlStore(db_path=db_path)

        retrieval_runner = RetrievalRunner(store=knowledge_store, config=self._retrieval_config)
        allowed_categories = frozenset(load_categories(Path("config/categories.yaml")))
        tool_executor = KBToolExecutor(
            retrieval_runner=retrieval_runner,
            retrieval_config=self._retrieval_config,
            allowed_categories=allowed_categories,
            max_search_chunks=self._chat_config.agentic_loop.max_search_chunks,
            max_search_chars=self._chat_config.agentic_loop.max_search_chars,
            max_get_document_chars=self._chat_config.agentic_loop.max_get_document_chars,
            max_tool_calls_per_turn=self._chat_config.agentic_loop.max_tool_calls_per_turn,
            store=knowledge_store,
        )
        retriever = BaselineRetriever(
            retrieval_runner=retrieval_runner,
            store=knowledge_store,
            retrieval_config=self._retrieval_config,
            chat_config=self._chat_config,
        )

        categories_config = Path("config/categories.yaml")
        ingest_definition: SagaDefinition[IngestInput, IngestData] = SagaDefinition(
            name="ingest",
            steps=[
                LoadSource(),
                PreprocessText(),
                DetectTargetSchema(categories_config=categories_config),
                SplitControlBlocks(
                    categories_config=categories_config,
                    date_suffix_config=self._ingest_config.date_suffix_config,
                ),
                ParseToTokens(),
                BuildSectionPath(),
                ChunkifyBlocks(
                    admin_headings=self._ingest_config.admin_section_headings,
                    max_section_chars=self._ingest_config.max_section_chars,
                ),
                Tagging(),
                PersistDocument(store=knowledge_store),
                PersistChunks(store=knowledge_store),
            ],
        )
        ingest_runner: SagaRunner[IngestInput, IngestData] = SagaRunner(
            ingest_definition, saga_store, IngestData
        )

        profile_service = ProfileService(internal_store=internal_store)
        sessions_service = SessionsService(internal_store=internal_store)
        ingest_service = IngestService(
            saga_runner=ingest_runner,
            knowledge_store=knowledge_store,
        )
        documents_service = DocumentsService(knowledge_store=knowledge_store)
        chat_service = ChatService(
            internal_store=internal_store,
            knowledge_store=knowledge_store,
            llm_client=self._llm_client,
            tool_executor=tool_executor,
            retriever=retriever,
            chat_config=self._chat_config,
            profile_service=profile_service,
            system_template=self._system_template,
            user_template=self._user_template,
        )

        return UserContext(
            username=username,
            db_path=db_path,
            sessions_service=sessions_service,
            profile_service=profile_service,
            ingest_service=ingest_service,
            documents_service=documents_service,
            chat_service=chat_service,
        )
