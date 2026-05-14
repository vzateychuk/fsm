import asyncio
import logging
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from commons import setup_logging
from fsm.core import SagaDefinition
from fsm.saga_runner import SagaRunner
from pipelines.medical_indexer.models import MedDocInput, MedDocData
from pipelines.medical_indexer.steps import (
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
    """Medical document indexer: process markdown files for FTS5 indexing (11 steps)"""

    setup_logging(level=logging.DEBUG, log_file="logs/medical_indexer.log")
    logger = logging.getLogger(__name__)

    definition = SagaDefinition[MedDocInput, MedDocData](
        name="medical_indexer",
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
    runner = SagaRunner(definition, store, MedDocData)

    logger.info("===> Before run <===")

    # Create sample markdown file
    sample_md = """%%medical_schema
---
title: Sample Medical Document
version: 1.0
---
# Introduction
This is a sample medical document for testing.

## Section 1
Content of section 1 with medical information.

### Subsection 1.1
Detailed medical information here.

## Section 2
More medical content.
"""
    sample_file = Path("sample_medical.md")
    sample_file.write_text(sample_md)

    try:
        ctx = await runner.run(
            run_id="medical-001",
            input=MedDocInput(source_path=str(sample_file)),
            initial_state=MedDocData(),
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
