"""Ingest CLI — process markdown documents into knowledge base."""
from __future__ import annotations
import asyncio
import logging
import sys
from pathlib import Path

from uuid import uuid4

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import typer

from src.common.logging_config import setup_logging
from src.fsm.core import SagaDefinition
from src.fsm.saga_runner import SagaRunner
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
from src.store.file.local_file_store import LocalFileStore
from src.store.sql.sql_store import SqlStore
from src.store.sql.sqlite_knowledge_store import SqliteKnowledgeStore


app = typer.Typer(add_completion=False)


async def init_schema(db_path: str | Path) -> None:
    schema = (Path(__file__).parent.parent / "store" / "sql" / "schema.sql").read_text()
    import aiosqlite  # lazy load to avoid import at top when not used
    async with aiosqlite.connect(db_path) as conn:
        await conn.executescript(schema)



@app.command()
def ingest(
    file: Path = typer.Argument(..., help="Path to the .md file to ingest"),
    config: Path = typer.Option(Path("config/ingest.yaml"), "--config", help="Path to ingest.yaml configuration"),
    db: Path = typer.Option(Path(".data/db/ingest.db"), "--db", help="Path to SQLite DB"),
    filestore: Path = typer.Option(Path(".data/filestore"), "--filestore", help="Path to file store"),
    run_id: str | None = typer.Option(None, "--run-id", help="Optional unique ID for resuming ingestion"),
) -> None:
    """Ingest a single markdown document into the knowledge base pipeline.

    Examples:
        python src/main/ingest.py .data/ingest/some_doc.md
        python src/main/ingest.py .data/ingest/some_doc.md --config ./config/my_ingest.yaml --db ./data/my_ingest.db
    """
    # coerce paths
    file = file.resolve()
    config = config.resolve()
    db = db.resolve()
    filestore = filestore.resolve()

    log_file = Path("logs/ingest.log")
    log_file.parent.mkdir(parents=True, exist_ok=True)
    setup_logging(level=logging.DEBUG, log_file=log_file)
    logger = logging.getLogger(__name__)

    logger.info("Ingest CLI invoked: %s", file)
    logger.info("Using config: %s", config)
    logger.info("Using DB: %s", db)
    logger.info("Using Filestore: %s", filestore)

    ingest_config = IngestConfig.load(config)

    asyncio.run(init_schema(db))

    knowledge_store = SqliteKnowledgeStore(db_path=db)
    saga_store = SqlStore(db_path=db)
    file_store = LocalFileStore(filestore_dir=filestore)

    definition = SagaDefinition[IngestInput, IngestData](
        name="ingest",
        steps=[
            LoadSource(),
            PreprocessText(),
            DetectTargetSchema(categories_config=Path("config/categories.yaml")),
            SplitControlBlocks(categories_config=Path("config/categories.yaml")),
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

    runner = SagaRunner(definition, saga_store, IngestData)

    run_id = run_id or f"ingest-{uuid4().hex[:8]}"
    logger.info("Pipeline run_id: %s", run_id)

    if not file.exists():
        logger.error("Document file not found: %s", file)
        sys.exit(1)

    try:
        ctx = asyncio.run(runner.run(
            run_id=run_id,
            input=IngestInput(source_path=str(file)),
            initial_data=IngestData(),
        ))
        logger.info("<=== Ingestion completed ===>")
        logger.info("Document desc: %s", ctx.data.desc)
        logger.info("Document ID: %s", ctx.data.document_id)
        logger.info("Chunks created: %d", len(ctx.data.chunk_ids))
        logger.info("FTS updated: %s", ctx.data.fts_updated)
    except Exception as e:
        logger.error("Pipeline run failed: %s", e, exc_info=True)
        sys.exit(1)



if __name__ == "__main__":
    app()
