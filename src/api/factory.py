"""Application factory — SharedContext and schema helpers."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path

from src.api.config import ApiConfig
from src.api.user_context import SharedContext, UserContext, UserContextFactory
from src.api.schema_init import ensure_system_schema
from src.api.user_db_paths import default_system_db_path, resolve_env_db_path, resolve_env_username
from src.chat.config import ChatConfig
from src.llm.config import LLMConfig
from src.llm.openai_client import OpenAICompatibleClient
from src.llm.retry_client import RetryConfig, RetryLLMClient
from src.pipelines.ingest.config import IngestConfig
from src.pipelines.retrieval.config import RetrievalConfig
from src.services.auth import AuthService
from src.store.sql.sqlite_system_store import SqliteSystemStore

logger = logging.getLogger(__name__)


@dataclass
class AppContext:
    """CLI compatibility wrapper around UserContext."""

    user_ctx: UserContext

    @property
    def sessions_service(self):
        return self.user_ctx.sessions_service

    @property
    def profile_service(self):
        return self.user_ctx.profile_service

    @property
    def ingest_service(self):
        return self.user_ctx.ingest_service

    @property
    def documents_service(self):
        return self.user_ctx.documents_service

    @property
    def chat_service(self):
        return self.user_ctx.chat_service

    @property
    def api_config(self):
        return self._api_config

    def __init__(self, user_ctx: UserContext, api_config: ApiConfig) -> None:
        self.user_ctx = user_ctx
        self._api_config = api_config


def _build_llm_client(llm_config: LLMConfig) -> OpenAICompatibleClient | RetryLLMClient:
    base_client = OpenAICompatibleClient(config=llm_config)
    if llm_config.retry_timeout_errors:
        retry_config = RetryConfig(
            max_retries=llm_config.retry_timeout_max_attempts - 1,
            initial_delay_sec=llm_config.retry_timeout_initial_delay,
            max_delay_sec=llm_config.retry_timeout_max_delay,
            backoff_factor=llm_config.retry_timeout_backoff_factor,
        )
        return RetryLLMClient(base_client, retry_config)
    return base_client


async def create_shared_context(
    api_config_path: Path = Path("config/api.yaml"),
) -> SharedContext:
    """Build process-wide shared context (LLM, auth, user factory)."""
    api_config = ApiConfig.load(api_config_path)
    llm_config = LLMConfig.load(Path("config/llm.yaml"))
    chat_config = ChatConfig.load(Path("config/chat.yaml"))
    retrieval_config = RetrievalConfig.load(Path("config/retrieve.yaml"))
    ingest_config = IngestConfig.load(Path("config/ingest.yaml"))

    llm_client = _build_llm_client(llm_config)
    system_template = Path("prompts/chat/system.md").read_text(encoding="utf-8")
    user_template = Path("prompts/chat/user.md").read_text(encoding="utf-8")

    user_factory = UserContextFactory(
        llm_client=llm_client,
        chat_config=chat_config,
        retrieval_config=retrieval_config,
        ingest_config=ingest_config,
        system_template=system_template,
        user_template=user_template,
    )

    system_db = default_system_db_path()
    await ensure_system_schema(system_db)
    system_store = SqliteSystemStore(db_path=system_db)
    auth_service = AuthService(system_store, user_factory)

    logger.info("SharedContext initialized (system_db=%s)", system_db)
    return SharedContext(
        api_config=api_config,
        auth_service=auth_service,
        user_factory=user_factory,
    )


async def create_cli_user_context(
    shared: SharedContext | None = None,
    *,
    username: str | None = None,
    db_path: str | None = None,
) -> UserContext:
    """Resolve user from env/CLI flags and return UserContext."""
    if shared is None:
        shared = await create_shared_context()
    user = username or resolve_env_username()
    path = db_path or resolve_env_db_path(user)
    return await shared.user_factory.get(user, path)


async def create_app_context(
    api_config_path: Path = Path("config/api.yaml"),
) -> AppContext:
    """CLI entry: shared context + env-resolved user."""
    shared = await create_shared_context(api_config_path)
    user_ctx = await create_cli_user_context(shared)
    return AppContext(user_ctx, shared.api_config)
