"""Test document_date extraction and retrieval."""

import tempfile
from datetime import datetime, UTC
from pathlib import Path
from unittest.mock import patch

import pytest

from pipelines.ingest.models import IngestData, IngestInput
from pipelines.ingest.steps.split_control_blocks import SplitControlBlocks
from fsm.core import RunContext
from store.sql.sqlite_knowledge_store import SqliteKnowledgeStore


@pytest.mark.asyncio
async def test_split_control_blocks_extracts_yaml_date():
    """Test that YAML metadata is parsed and document_date is extracted."""
    fixture_path = Path(__file__).parent / "fixtures" / "ingest" / "with_metadata.md"
    content = fixture_path.read_text(encoding="utf-8")

    ctx = RunContext[IngestInput, IngestData](
        run_id="test-run",
        saga_name="test-ingest",
        cursor=0,
        input=IngestInput(source_path=str(fixture_path)),
        data=IngestData(raw_content=content),
    )

    config = Path(__file__).parents[1] / "config" / "categories.yaml"
    step = SplitControlBlocks(categories_config=config)
    await step.run(ctx)

    assert ctx.data.document_date == "2025-06-15", "document_date should be extracted from YAML metadata"
    assert "# УЗИ сердца" in ctx.data.md_body, "Markdown body should contain main content"


@pytest.mark.asyncio
async def test_list_documents_by_date():
    """Test list_documents_by_date returns documents in correct order."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        store = SqliteKnowledgeStore(db_path=str(db_path))

        # Initialize database schema
        import aiosqlite
        async with aiosqlite.connect(str(db_path)) as conn:
            schema_path = Path(__file__).parents[1] / "src" / "store" / "sql" / "schema.sql"
            schema = schema_path.read_text()
            await conn.executescript(schema)
            await conn.commit()

        # Save documents with different dates
        await store.save_document(
            document_id="doc1",
            source_path="file1.md",
            source_sha256="abc123",
            category="Диагноз",
            indexed_at="2025-01-01T10:00:00+00:00",
            document_date="2025-06-15",
            raw_text="Content 1",
        )

        await store.save_document(
            document_id="doc2",
            source_path="file2.md",
            source_sha256="def456",
            category="Диагноз",
            indexed_at="2025-01-02T10:00:00+00:00",
            document_date="2025-06-10",
            raw_text="Content 2",
        )

        await store.save_document(
            document_id="doc3",
            source_path="file3.md",
            source_sha256="ghi789",
            category="Анализ",
            indexed_at="2025-01-03T10:00:00+00:00",
            document_date="2025-01-03",  # No explicit date in content, would fallback to current date
            raw_text="Content 3",
        )

        # Test list_documents_by_date without filter
        results = await store.list_documents_by_date(limit=5)
        assert len(results) == 3
        # Most recent should be first (doc1 with 2025-06-15)
        assert results[0].document_id == "doc1"
        assert results[0].document_date == "2025-06-15"

        # Test with category filter
        results = await store.list_documents_by_date(limit=5, category="Диагноз")
        assert len(results) == 2
        assert results[0].document_id == "doc1"
        assert results[1].document_id == "doc2"

        # Test limit
        results = await store.list_documents_by_date(limit=1)
        assert len(results) == 1
        assert results[0].document_id == "doc1"


@pytest.mark.asyncio
async def test_fallback_to_current_date_when_extraction_fails(caplog):
    """Test that when document_date cannot be extracted, fallback uses current date with warning."""
    # File with no date in name and no date markers in content
    fixture_path = Path(__file__).parent / "fixtures" / "ingest" / "minimal_valid.md"
    content = fixture_path.read_text(encoding="utf-8")

    ctx = RunContext[IngestInput, IngestData](
        run_id="test-run",
        saga_name="test-ingest",
        cursor=0,
        input=IngestInput(source_path=str(fixture_path)),
        data=IngestData(raw_content=content),
    )

    config = Path(__file__).parents[1] / "config" / "categories.yaml"
    step = SplitControlBlocks(categories_config=config)

    with caplog.at_level("WARNING"):
        await step.run(ctx)

    # document_date should be set to current date (today)
    today = datetime.now(UTC).date().isoformat()
    assert ctx.data.document_date == today

    # Check that warning was logged
    assert "Could not extract document date" in caplog.text
    assert "Using current date as fallback" in caplog.text
