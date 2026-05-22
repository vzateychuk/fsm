import asyncio
import logging
import os
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import aiosqlite

from common import setup_logging
from fsm.core import SagaDefinition
from fsm.saga_runner import SagaRunner
from pipelines.ingest.config import IngestConfig
from pipelines.ingest.models import IngestData, IngestInput
from pipelines.ingest.steps import (
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
from store.file.local_file_store import LocalFileStore
from store.sql.sql_store import SqlStore
from store.sql.sqlite_knowledge_store import SqliteKnowledgeStore


async def init_schema(db_path: str) -> None:
    schema = (Path(__file__).parent.parent / "store" / "sql" / "schema.sql").read_text()
    async with aiosqlite.connect(db_path) as conn:
        await conn.executescript(schema)


async def main() -> None:
    """Runner for Document ingestion pipeline: process markdown files for FTS5 indexing (10 steps)"""

    log_file = os.getenv("LOG_FILE", "logs/ingest.log")
    setup_logging(level=logging.DEBUG, log_file=log_file)
    logger = logging.getLogger(__name__)

    logger.info(f"[INFO] Logs directory: {os.path.abspath(os.path.dirname(log_file))}")
    logger.info(f"[INFO] Log file: {os.path.abspath(log_file)}")

    db_path = os.getenv("DB_PATH", ".data/db/ingest.db")
    await init_schema(db_path)

    knowledge_store = SqliteKnowledgeStore(db_path=db_path)
    saga_store = SqlStore(db_path=db_path)
    file_store = LocalFileStore(filestore_dir=os.getenv("FILESTORE_DIR", ".data/filestore"))

    categories_config = Path(__file__).parents[2] / "config" / "categories.yaml"
    ingest_config_path = Path(__file__).parents[2] / "config" / "ingest.yaml"
    ingest_config = IngestConfig.load(ingest_config_path)

    definition = SagaDefinition[IngestInput, IngestData](
        name="ingest",
        steps=[
            LoadSource(),
            PreprocessText(),
            DetectTargetSchema(categories_config=categories_config),
            SplitControlBlocks(categories_config=categories_config),
            ParseToTokens(),
            BuildSectionPath(),
            ChunkifyBlocks(admin_headings=ingest_config.admin_section_headings),
            Tagging(),
            PersistSourceFile(store=file_store),
            PersistDocument(store=knowledge_store),
            PersistChunks(store=knowledge_store),
        ],
    )

    runner = SagaRunner(definition, saga_store, IngestData)

    logger.info("===> Before run <===")

    ingest_file = Path(os.getenv("INGEST_FILE", "tests/fixtures/ingest/consultation_deep.md")).absolute()

    if not ingest_file.exists():
        logger.error(f"Document file not found: {ingest_file}")
        sys.exit(1)

    # Генерировать уникальный run_id для каждого нового запуска
    # Если пользователь передал INGEST_RUN_ID, использовать его (для возобновления)
    run_id = os.getenv("INGEST_RUN_ID") or f"ingest-{uuid.uuid4().hex[:8]}"
    logger.info(f"Pipeline run_id: {run_id}")

    try:
        ctx = await runner.run(
            run_id=run_id,
            input=IngestInput(source_path=str(ingest_file)),
            initial_data=IngestData(),
        )

        logger.info("<=== After run ===>")
        logger.info(f"Final desc: {ctx.data.desc}")
        logger.info(f"Document ID: {ctx.data.document_id}")
        logger.info(f"Chunks created: {len(ctx.data.chunk_ids)}")
        logger.info(f"FTS updated: {ctx.data.fts_updated}")
    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
