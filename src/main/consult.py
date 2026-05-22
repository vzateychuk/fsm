"""Debug script for ConsultRunner — allows step-by-step debugging in VS Code."""

import asyncio
import os
from pathlib import Path

from src.llm.mock import MockLLMClient
from src.pipelines.consult.config import ConsultConfig
from src.pipelines.consult.models import ConsultRequest
from src.pipelines.consult.runner import ConsultRunner
from src.pipelines.retrieval.config import RetrievalConfig
from src.pipelines.retrieval.runner import RetrievalRunner
from src.store.sql.sqlite_knowledge_store import SqliteKnowledgeStore
from src.common.logging_config import setup_logging


async def main():
    setup_logging()

    # Configuration
    db_path = os.getenv("DB_PATH", ".data/db/ingest.db")
    consult_config = ConsultConfig.load(Path("config/consult.yaml"))
    retrieval_config = RetrievalConfig.load(Path("config/retrieve.yaml"))

    # Initialize components
    store = SqliteKnowledgeStore(db_path=db_path)
    retrieval_runner = RetrievalRunner(store, retrieval_config)

    # Use mock LLM for debugging
    mock_llm = MockLLMClient(fixed_response="Mock debug response.")

    # Create runner with all dependencies injected
    runner = ConsultRunner(
        retrieval_runner=retrieval_runner,
        retrieval_config=retrieval_config,
        store=store,
        llm_client=mock_llm,
        consult_config=consult_config,
        prompts_dir=Path("prompts"),
    )

    # Execute pipeline
    request = ConsultRequest(user_request="болит живот справа, температура 37.8")
    result = await runner.run(request)

    print(f"\n=== Pipeline Result ===")
    print(f"User request: {result.user_request}")
    print(f"Bundle top_chunks: {len(result.bundle.top_chunks) if result.bundle else 0}")
    print(f"Bundle kb_excerpts: {len(result.bundle.kb_excerpts) if result.bundle else 0}")
    print(f"{result.response.raw_text if result.response else 'None'}")


if __name__ == "__main__":
    asyncio.run(main())