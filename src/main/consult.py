"""Medical consultation CLI — Typer entry point."""
from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import typer

from src.common.logging_config import setup_logging
from src.llm.mock import MockLLMClient
from src.llm.openai_client import OpenAICompatibleClient
from src.pipelines.consult.config import ConsultConfig, LLMConfig
from src.pipelines.consult.models import ConsultRequest
from src.pipelines.consult.runner import ConsultRunner
from src.pipelines.retrieval.config import RetrievalConfig
from src.pipelines.retrieval.runner import RetrievalRunner
from src.store.sql.sqlite_knowledge_store import SqliteKnowledgeStore

app = typer.Typer(add_completion=False)


@app.command()
def consult(
    user_request: str,
    config_path: Path = typer.Option(Path("config/consult.yaml"), "--config"),
    env: str = typer.Option("prod", "--env", help="prod | test"),
    from_date: str = typer.Option(None, "--from-date", help="Search from date (ISO format YYYY-MM-DD)"),
    to_date: str = typer.Option(None, "--to-date", help="Search to date (ISO format YYYY-MM-DD)"),
    include_meta: bool = typer.Option(False, "--include-meta", help="Include administrative (meta) chunks in search results"),
) -> None:
    """Medical consultation: user request -> retrieval KB -> LLM response.

    Optional date filtering:
        --from-date YYYY-MM-DD    Search documents from this date onwards
        --to-date YYYY-MM-DD      Search documents up to this date
    """
    setup_logging(level=logging.INFO)
    logger = logging.getLogger(__name__)

    consult_config = ConsultConfig.load(config_path)
    retrieval_config = RetrievalConfig.load(Path("config/retrieve.yaml"))
    db_path = os.getenv("DB_PATH", ".data/db/default.db")
    store = SqliteKnowledgeStore(db_path=db_path)
    retrieval_runner = RetrievalRunner(store=store, config=retrieval_config)

    llm_config = LLMConfig.load(Path("config/llm.yaml"))
    if env == "test":
        llm_client: MockLLMClient | OpenAICompatibleClient = MockLLMClient()
    else:
        llm_client = OpenAICompatibleClient(config=llm_config)

    runner = ConsultRunner(
        retrieval_runner=retrieval_runner,
        retrieval_config=retrieval_config,
        store=store,
        llm_client=llm_client,
        consult_config=consult_config,
        prompts_dir=Path("prompts"),
    )

    logger.info("Starting consultation: %r", user_request)
    result = asyncio.run(runner.run(ConsultRequest(user_request=user_request, from_date=from_date, to_date=to_date, include_meta_chunks=include_meta)))
    logger.info("Consultation complete.")
    print(result.response.raw_text if result.response else "")


if __name__ == "__main__":
    app()
