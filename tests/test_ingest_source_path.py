"""Tests that ingest persists original upload filename in documents.source_path."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import aiosqlite
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from fsm.core import RunContext
from pipelines.ingest.models import IngestData, IngestInput
from pipelines.ingest.steps.persist_document import PersistDocument
from store.sql.sqlite_knowledge_store import SqliteKnowledgeStore


@pytest.mark.asyncio
async def test_persist_document_saves_original_filename(tmp_path: Path) -> None:
    db_path = tmp_path / "ingest.db"
    schema = (
        Path(__file__).parent.parent / "src" / "store" / "sql" / "schema.sql"
    ).read_text(encoding="utf-8")
    async with aiosqlite.connect(str(db_path)) as conn:
        await conn.executescript(schema)

    store = SqliteKnowledgeStore(db_path=str(db_path))
    step = PersistDocument(store=store)

    ctx = RunContext[IngestInput, IngestData](
        run_id="test-run",
        saga_name="ingest",
        cursor=0,
        input=IngestInput(
            source_path="/tmp/tmpxyz.md",
            original_filename="2024-10-13_clinic.md",
        ),
        data=IngestData(
            file_hash="a" * 64,
            target_schema="Консультация",
            document_date="2024-10-13",
            raw_content="**Категория:** Консультация\n\nBody",
        ),
    )

    await step.run(ctx)

    doc = await store.get_document_metadata(ctx.data.document_id)
    assert doc is not None
    assert doc.source_path == "2024-10-13_clinic.md"
