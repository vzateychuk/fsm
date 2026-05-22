"""Integration tests for consultation pipeline."""

import tempfile
from pathlib import Path

import aiosqlite
import pytest

from src.llm import MockLLMClient
from src.pipelines.consult.config import ConsultConfig
from src.pipelines.consult.models import ConsultRequest
from src.pipelines.consult.runner import ConsultRunner
from src.pipelines.retrieval.config import RetrievalConfig
from src.pipelines.retrieval.runner import RetrievalRunner
from src.store.sql.sqlite_knowledge_store import SqliteKnowledgeStore


@pytest.fixture
async def test_db() -> str:
    """Create an in-memory test database with schema."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test.db")

        async with aiosqlite.connect(db_path) as conn:
            schema_path = Path("src/store/sql/schema.sql")
            schema = schema_path.read_text()
            for stmt in schema.split(";"):
                if stmt.strip():
                    await conn.execute(stmt)
            await conn.commit()

        # Populate with test data
        async with aiosqlite.connect(db_path) as conn:
            await conn.execute(
                "INSERT INTO documents (id, source_path, source_sha256, category, indexed_at, document_date, raw_text)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    "doc_recent",
                    "recent.md",
                    "sha256_recent",
                    "MedicalReport",
                    "2026-05-20T00:00:00",
                    "2026-05-20",
                    "This is a recent document.",
                ),
            )
            await conn.execute(
                "INSERT INTO documents (id, source_path, source_sha256, category, indexed_at, document_date, raw_text)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    "doc_old",
                    "old.md",
                    "sha256_old",
                    "MedicalReport",
                    "2020-01-01T00:00:00",
                    "2020-01-01",
                    "This is an old document.",
                ),
            )

            # Add chunks to recent doc
            await conn.execute(
                "INSERT INTO chunks (chunk_id, document_id, chunk_no, kind, text, section_path, heading, tags_text)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    "chunk_recent_1",
                    "doc_recent",
                    0,
                    "fact",
                    "Recent finding 1",
                    None,
                    None,
                    None,
                ),
            )
            await conn.execute(
                "INSERT INTO chunks (chunk_id, document_id, chunk_no, kind, text, section_path, heading, tags_text)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    "chunk_recent_2",
                    "doc_recent",
                    1,
                    "fact",
                    "Recent finding 2",
                    None,
                    None,
                    None,
                ),
            )

            # Add chunks to old doc (should be filtered out)
            await conn.execute(
                "INSERT INTO chunks (chunk_id, document_id, chunk_no, kind, text, section_path, heading, tags_text)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    "chunk_old_1",
                    "doc_old",
                    0,
                    "fact",
                    "Old finding 1",
                    None,
                    None,
                    None,
                ),
            )

            await conn.commit()

        yield db_path


@pytest.mark.asyncio
async def test_consult_pipeline_end_to_end(test_db: str) -> None:
    """Integration test: end-to-end consultation with mock LLM."""
    config = ConsultConfig.load("config/consult.yaml")
    store = SqliteKnowledgeStore(db_path=test_db)

    retrieval_config = RetrievalConfig.load(Path("config/retrieve.yaml"))
    retrieval_runner = RetrievalRunner(store, retrieval_config)

    mock_llm = MockLLMClient(fixed_response="Test medical answer from LLM.")
    prompts_dir = Path("prompts")

    runner = ConsultRunner(
        retrieval_runner=retrieval_runner,
        retrieval_config=retrieval_config,
        store=store,
        llm_client=mock_llm,
        consult_config=config,
        prompts_dir=prompts_dir,
    )

    result = await runner.run(ConsultRequest(user_request="болит живот"))

    assert result.response is not None
    assert result.response.raw_text == "Test medical answer from LLM."
    assert mock_llm.last_request is not None
    assert len(mock_llm.last_request.messages) == 2
    assert mock_llm.last_request.messages[0].role == "system"
    assert mock_llm.last_request.messages[1].role == "user"


@pytest.mark.asyncio
async def test_consult_pipeline_recency_filter(test_db: str) -> None:
    """Test that old documents are filtered out by date."""
    config = ConsultConfig.load("config/consult.yaml")
    store = SqliteKnowledgeStore(db_path=test_db)

    retrieval_config = RetrievalConfig.load(Path("config/retrieve.yaml"))
    retrieval_runner = RetrievalRunner(store, retrieval_config)

    mock_llm = MockLLMClient(fixed_response="Mock answer")
    prompts_dir = Path("prompts")

    runner = ConsultRunner(
        retrieval_runner=retrieval_runner,
        retrieval_config=retrieval_config,
        store=store,
        llm_client=mock_llm,
        consult_config=config,
        prompts_dir=prompts_dir,
    )

    result = await runner.run(ConsultRequest(user_request="test"))

    assert len(result.recency_chunks) == 2
    assert all(c.document_id == "doc_recent" for c in result.recency_chunks)


@pytest.mark.asyncio
async def test_consult_pipeline_bundle_assembly(test_db: str) -> None:
    """Test that bundle is properly assembled with top_chunks and kb_excerpts."""
    config = ConsultConfig.load("config/consult.yaml")
    store = SqliteKnowledgeStore(db_path=test_db)

    retrieval_config = RetrievalConfig.load(Path("config/retrieve.yaml"))
    retrieval_runner = RetrievalRunner(store, retrieval_config)

    mock_llm = MockLLMClient(fixed_response="Mock")
    prompts_dir = Path("prompts")

    runner = ConsultRunner(
        retrieval_runner=retrieval_runner,
        retrieval_config=retrieval_config,
        store=store,
        llm_client=mock_llm,
        consult_config=config,
        prompts_dir=prompts_dir,
    )

    result = await runner.run(ConsultRequest(user_request="test"))

    assert result.bundle is not None
    assert isinstance(result.bundle.top_chunks, list)
    assert isinstance(result.bundle.kb_excerpts, list)
    assert isinstance(result.bundle.provenance, list)


@pytest.mark.asyncio
async def test_consult_pipeline_empty_retrieval(test_db: str) -> None:
    """Test pipeline with empty retrieval results."""
    config = ConsultConfig.load("config/consult.yaml")
    store = SqliteKnowledgeStore(db_path=test_db)

    retrieval_config = RetrievalConfig.load(Path("config/retrieve.yaml"))
    retrieval_runner = RetrievalRunner(store, retrieval_config)

    mock_llm = MockLLMClient(fixed_response="No results found")
    prompts_dir = Path("prompts")

    runner = ConsultRunner(
        retrieval_runner=retrieval_runner,
        retrieval_config=retrieval_config,
        store=store,
        llm_client=mock_llm,
        consult_config=config,
        prompts_dir=prompts_dir,
    )

    result = await runner.run(
        ConsultRequest(user_request="completely_nonexistent_query_xyz")
    )

    assert result.response is not None
    assert result.response.raw_text == "No results found"
