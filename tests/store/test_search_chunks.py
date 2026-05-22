"""Unit tests for SqliteKnowledgeStore.search_chunks — meta_score_factor penalty."""

from __future__ import annotations

import sys
from pathlib import Path

# Add src to path before any imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import aiosqlite
import pytest

from store.sql.sqlite_knowledge_store import SqliteKnowledgeStore

def _schema_path() -> Path:
    return Path(__file__).parent.parent.parent / "src" / "store" / "sql" / "schema.sql"


_CLINICAL_CHUNK: dict = {
    "kind": "section",
    "text": "боль в животе справа острая диагноз жалобы и анамнез",
    "section_path": "острый аппендицит > жалобы и анамнез",
    "heading": "Жалобы и анамнез",
    "tags_text": "section жалобы анамнез аппендицит диагноз",
}

_META_CHUNK: dict = {
    "kind": "meta",
    "text": "боль в животе справа повышенная температура возраст пол",
    "section_path": "острый аппендицит > информация о пациенте",
    "heading": "Информация о пациенте",
    "tags_text": "meta информация пациент",
}


async def _init_schema(db_path: str) -> None:
    schema = _schema_path().read_text(encoding="utf-8")
    async with aiosqlite.connect(db_path) as conn:
        await conn.executescript(schema)


@pytest.fixture
async def store_with_chunks(tmp_path: Path) -> SqliteKnowledgeStore:
    db_path = str(tmp_path / "test_meta.db")
    await _init_schema(db_path)

    store = SqliteKnowledgeStore(db_path=db_path)
    await store.save_document(
        document_id="doc1",
        source_path="appendicitis.md",
        source_sha256="abc" * 21 + "ab",
        category="Диагноз",
        indexed_at="2026-01-01",
        document_date="2026-01-01",
        raw_text="full document text",
    )
    await store.replace_document_chunks(
        document_id="doc1",
        chunks=[_CLINICAL_CHUNK, _META_CHUNK],  # type: ignore[arg-type]
    )
    return store


class TestMetaScoreFactor:
    async def test_meta_deprioritized_with_factor_0_1(
        self, store_with_chunks: SqliteKnowledgeStore
    ) -> None:
        results = await store_with_chunks.search_chunks(
            "боль* OR живот* OR справа*",
            meta_score_factor=0.1,
            limit=10,
            limit_per_document=10,
        )

        assert len(results) == 2
        kinds = [r.kind for r in results]
        section_idx = kinds.index("section")
        meta_idx = kinds.index("meta")
        assert section_idx < meta_idx, (
            f"section chunk must rank before meta chunk when meta_score_factor=0.1, "
            f"got order: {kinds}"
        )

    async def test_meta_present_but_last_with_factor_0_1(
        self, store_with_chunks: SqliteKnowledgeStore
    ) -> None:
        results = await store_with_chunks.search_chunks(
            "боль* OR живот* OR справа*",
            meta_score_factor=0.1,
            limit=10,
            limit_per_document=10,
        )

        assert any(r.kind == "meta" for r in results), "meta chunk must still appear in results (not filtered)"

    async def test_meta_not_penalized_with_factor_1_0(
        self, store_with_chunks: SqliteKnowledgeStore
    ) -> None:
        results = await store_with_chunks.search_chunks(
            "боль* OR живот* OR справа*",
            meta_score_factor=1.0,
            limit=10,
            limit_per_document=10,
        )

        assert len(results) == 2
        # meta chunk has more unique tokens matching query → higher TF → ranks first without penalty
        assert results[0].kind == "meta", (
            "without penalty meta chunk should rank first due to higher term concentration"
        )

    async def test_factor_exactly_1_0_skips_penalty_code_path(
        self, store_with_chunks: SqliteKnowledgeStore
    ) -> None:
        """meta_score_factor=1.0 must not apply any penalty (code path: if factor < 1.0)."""
        results_penalized = await store_with_chunks.search_chunks(
            "боль* OR живот* OR справа*",
            meta_score_factor=0.1,
            limit=10,
            limit_per_document=10,
        )
        results_unpenalized = await store_with_chunks.search_chunks(
            "боль* OR живот* OR справа*",
            meta_score_factor=1.0,
            limit=10,
            limit_per_document=10,
        )

        penalized_order = [r.kind for r in results_penalized]
        unpenalized_order = [r.kind for r in results_unpenalized]
        assert penalized_order != unpenalized_order, (
            "penalized and unpenalized results must differ in chunk order"
        )
