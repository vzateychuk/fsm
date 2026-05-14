import asyncio
import logging
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
    BuildSectionPath,
    ChunkifyBlocks,
    Tagging,
    PersistDocument,
    PersistChunks,
    UpdateFTS,
)
from store.inmem.inmemory_store import InMemoryStore


async def main() -> None:
    """Document ingestion pipeline: process markdown files for FTS5 indexing (11 steps)"""

    setup_logging(level=logging.DEBUG, log_file="logs/ingest.log")
    logger = logging.getLogger(__name__)

    definition = SagaDefinition[IngestInput, IngestData](
        name="ingest",
        steps=[
            LoadSource(),
            PreprocessText(),
            DetectTargetSchema(),
            SplitControlBlocks(),
            ParseToTokens(),
            BuildSectionPath(),
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

    # Create sample markdown file
    sample_md = """%%document
---
title: Sample Document
version: 1.0
---
# Introduction
This is a sample document for testing.

## Section 1
Content of section 1 with information.

### Subsection 1.1
Detailed information here.

## Section 2
More content.
"""
    sample_file = Path("sample_document.md")
    sample_file.write_text(sample_md)

    try:
        ctx = await runner.run(
            run_id="ingest-001",
            input=IngestInput(source_path=str(sample_file)),
            initial_data=IngestData(),
        )

        logger.info("<=== After run ===>")
        logger.info(f"Final desc: {ctx.data.desc}")
        logger.info(f"Document ID: {ctx.data.document_id}")
        logger.info(f"Chunks created: {len(ctx.data.chunk_ids)}")
        logger.info(f"FTS updated: {ctx.data.fts_updated}")
    finally:
        # Cleanup
        if sample_file.exists():
            sample_file.unlink()


if __name__ == "__main__":
    asyncio.run(main())
