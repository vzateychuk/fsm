"""Integration tests for retrieval pipeline R0–R6 (Phase R2)."""

from __future__ import annotations

from pathlib import Path

import aiosqlite
import pytest
from pipelines.retrieval.config import RetrievalConfig
from pipelines.retrieval.models import RetrieveRequest
from pipelines.retrieval.runner import RetrievalRunner
from store.sql.sqlite_knowledge_store import SqliteKnowledgeStore


async def init_test_schema(db_path: str) -> None:
    """Initialize SQLite schema for testing."""
    # Path calculation: tests/retrieval/test_retrieval.py -> src/store/sql/schema.sql
    test_dir = Path(__file__).parent  # tests/retrieval
    schema_path = test_dir.parent.parent / "src" / "store" / "sql" / "schema.sql"
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema file not found at {schema_path}")
    schema = schema_path.read_text()
    async with aiosqlite.connect(db_path) as conn:
        await conn.executescript(schema)


@pytest.fixture
async def empty_db() -> str:
    """Create an empty SQLite database with schema initialized."""
    db_path = "test_retrieval_empty.db"
    await init_test_schema(db_path)
    yield db_path
    # Cleanup
    try:
        Path(db_path).unlink()
    except FileNotFoundError:
        pass


@pytest.fixture
def config() -> RetrievalConfig:
    """Retrieval config for testing."""
    return RetrievalConfig(
        limit=20,
        prelimit=200,
        limit_per_document=3,
        bm25_weights=(1.0, 2.5, 2.0, 3.5),
        enable_prefixes=True,
        prefix_min_len=5,
        category_mode="soft",
        debug=False,
    )


@pytest.fixture
def config_debug() -> RetrievalConfig:
    """Retrieval config with debug enabled."""
    return RetrievalConfig(
        limit=10,
        prelimit=100,
        limit_per_document=2,
        bm25_weights=(1.0, 2.5, 2.0, 3.5),
        enable_prefixes=True,
        prefix_min_len=5,
        category_mode="soft",
        debug=True,
    )


class TestRetrievalPipelineR0R6:
    """Test R0–R6 pipeline end-to-end (normalize → intent → aliases → FTS → search → group)."""

    async def test_normalize_query(self, config: RetrievalConfig, empty_db: str) -> None:
        """Test R1: Query normalization."""
        store = SqliteKnowledgeStore(db_path=empty_db)
        runner = RetrievalRunner(store=store, config=config)

        response = await runner.run(RetrieveRequest(query="Протрузия МРТ\r\n"))

        assert response.query_original == "Протрузия МРТ\r\n"
        assert response.query_normalized == "протрузия мрт"

    async def test_cyrillic_yo_normalization(self, config: RetrievalConfig, empty_db: str) -> None:
        """Test R1: ё → е conversion."""
        store = SqliteKnowledgeStore(db_path=empty_db)
        runner = RetrievalRunner(store=store, config=config)

        response = await runner.run(RetrieveRequest(query="ПТГ (ё)"))

        assert "е" in response.query_normalized or "ё" not in response.query_normalized

    async def test_fts_match_empty_when_no_db(self, config: RetrievalConfig, empty_db: str) -> None:
        """Test R0–R4: FTS match is built even with empty database."""
        store = SqliteKnowledgeStore(db_path=empty_db)
        runner = RetrievalRunner(store=store, config=config)

        response = await runner.run(RetrieveRequest(query="тест"))

        # fts_match should be non-empty after R4
        assert response.fts_match is not None
        # But chunks empty since DB is empty
        assert len(response.chunks) == 0
        assert len(response.documents) == 0

    async def test_debug_output_structure(self, config_debug: RetrievalConfig, empty_db: str) -> None:
        """Test R2.4: Debug output contains expected keys."""
        store = SqliteKnowledgeStore(db_path=empty_db)
        runner = RetrievalRunner(store=store, config=config_debug)

        response = await runner.run(RetrieveRequest(query="мрт узи"))

        assert response.debug is not None
        # Should have debug info from steps that matched keywords
        assert "alias_expansions" in response.debug
        assert "fts_match" in response.debug
        assert "search_chunks" in response.debug
        assert "group_by_document" in response.debug

    async def test_group_by_document_structure(self, config: RetrievalConfig, empty_db: str) -> None:
        """Test R6: GroupByDocument produces DocumentEvidence list."""
        store = SqliteKnowledgeStore(db_path=empty_db)
        runner = RetrievalRunner(store=store, config=config)

        # Empty DB test
        response = await runner.run(RetrieveRequest(query="test"))

        assert response.documents is not None
        assert isinstance(response.documents, list)

    async def test_diversity_filter_zero(self, config: RetrievalConfig, empty_db: str) -> None:
        """Test diversity disabled when limit_per_document=0."""
        store = SqliteKnowledgeStore(db_path=empty_db)
        runner = RetrievalRunner(store=store, config=config)

        request = RetrieveRequest(query="test", limit_per_document=0)
        response = await runner.run(request)

        # With limit_per_document=0, diversity should be disabled
        assert isinstance(response.chunks, list)


@pytest.mark.asyncio
async def test_e2e_pipeline_structure() -> None:
    """Full E2E test structure (requires real DB with indexed documents)."""
    db_path = "test_e2e.db"
    await init_test_schema(db_path)

    try:
        config = RetrievalConfig(debug=True)
        store = SqliteKnowledgeStore(db_path=db_path)
        runner = RetrievalRunner(store=store, config=config)

        response = await runner.run(RetrieveRequest(query="мрт"))

        # Verify response structure
        assert response.query_original == "мрт"
        assert response.query_normalized is not None
        assert response.fts_match is not None
        assert isinstance(response.chunks, list)
        assert isinstance(response.documents, list)
        assert response.debug is not None
    finally:
        Path(db_path).unlink(missing_ok=True)
