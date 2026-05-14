import asyncio
import logging
import os
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from commons import setup_logging
from fsm.core import SagaDefinition
from fsm.saga_runner import SagaRunner
from pipelines.ingest.models import IngestInput, IngestData
from pipelines.ingest.steps import (
    LoadSource,
    PreprocessText,
    DetectTargetSchema,
    SplitControlBlocks,
    ParseToTokens,
    ChunkifyBlocks,
    Tagging,
    PersistDocument,
    PersistChunks,
    UpdateFTS,
)
from store.inmem.inmemory_store import InMemoryStore


async def main() -> None:
    """Document ingestion pipeline: process markdown files for FTS5 indexing (10 steps)"""

    # Log file path can be set via LOG_FILE environment variable
    log_file = os.getenv("LOG_FILE", "logs/ingest.log")
    setup_logging(level=logging.DEBUG, log_file=log_file)
    logger = logging.getLogger(__name__)

    # Print log location info
    print(f"[INFO] Logs directory: {os.path.abspath(os.path.dirname(log_file))}")
    print(f"[INFO] Log file: {os.path.abspath(log_file)}")

    definition = SagaDefinition[IngestInput, IngestData](
        name="ingest",
        steps=[
            LoadSource(),
            PreprocessText(),
            DetectTargetSchema(),
            SplitControlBlocks(),
            ParseToTokens(),
            ChunkifyBlocks(),
            Tagging(),
            PersistDocument(),
            PersistChunks(),
            UpdateFTS(),
        ],
    )

    store = InMemoryStore()
    runner = SagaRunner(definition, store, IngestData)

    logger.info("===> Before run <===")

    # Load sample document from file system
    ingest_file = Path(os.getenv("INGEST_FILE", "tests/fixtures/ingest/consultation_deep.md"))

    if not ingest_file.exists():
        logger.error(f"Document file not found: {ingest_file}")
        sys.exit(1)

    try:
        ctx = await runner.run(
            run_id="ingest-001",
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
