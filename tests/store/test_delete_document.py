"""Unit tests for SqliteKnowledgeStore.delete_document."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import aiosqlite
import pytest

from store.sql.sqlite_knowledge_store import SqliteKnowledgeStore
from src.services.documents import DocumentsService
from src.services.errors import NotFoundError


def _schema_path() -> Path:
    return Path(__file__).parent.parent.parent / "src" / "store" / "sql" / "schema.sql"


async def _init_schema(db_path: str) -> None:
    schema = _schema_path().read_text(encoding="utf-8")
    async with aiosqlite.connect(db_path) as conn:
        await conn.executescript(schema)


_CHUNK: dict = {
    "kind": "section",
    "text": "клинический текст для поиска",
    "section_path": "документ > заключение",
    "heading": "Заключение",
    "tags_text": "section заключение",
}


@pytest.fixture
async def store(tmp_path: Path) -> SqliteKnowledgeStore:
    db_path = str(tmp_path / "test_delete.db")
    await _init_schema(db_path)
    return SqliteKnowledgeStore(db_path=db_path)


async def _seed_document(store: SqliteKnowledgeStore, document_id: str = "doc1") -> None:
    await store.save_document(
        document_id=document_id,
        source_path="test.md",
        source_sha256="abc" * 21 + "ab",
        category="Исследование",
        indexed_at="2026-06-06",
        document_date="2026-06-06",
        raw_text="full document text",
    )
    await store.replace_document_chunks(document_id=document_id, chunks=[_CHUNK])  # type: ignore[arg-type]


class TestDeleteDocument:
    async def test_delete_existing_document_removes_rows_and_fts(
        self, store: SqliteKnowledgeStore
    ) -> None:
        await _seed_document(store)

        deleted = await store.delete_document("doc1")
        assert deleted is True

        assert await store.get_document_metadata("doc1") is None
        assert await store.get_document_chunks("doc1", limit=10) == []

        results = await store.search_chunks("клинический", limit=10)
        assert results == []

    async def test_delete_missing_document_returns_false(
        self, store: SqliteKnowledgeStore
    ) -> None:
        assert await store.delete_document("missing") is False

    async def test_delete_does_not_affect_other_documents(
        self, store: SqliteKnowledgeStore
    ) -> None:
        await _seed_document(store, "doc1")
        await _seed_document(store, "doc2")

        assert await store.delete_document("doc1") is True

        assert await store.get_document_metadata("doc1") is None
        assert await store.get_document_metadata("doc2") is not None
        assert len(await store.get_document_chunks("doc2", limit=10)) == 1


class TestDocumentsServiceGetDocument:
    async def test_get_existing_returns_metadata_and_content(
        self, store: SqliteKnowledgeStore
    ) -> None:
        await _seed_document(store)
        service = DocumentsService(knowledge_store=store)

        doc = await service.get_document("doc1")

        assert doc is not None
        assert doc.metadata.document_id == "doc1"
        assert doc.metadata.source_path == "test.md"
        assert doc.metadata.category == "Исследование"
        assert doc.content == "full document text"

    async def test_get_missing_returns_none(self, store: SqliteKnowledgeStore) -> None:
        service = DocumentsService(knowledge_store=store)

        assert await service.get_document("missing") is None


class TestDocumentsServiceDeleteDocument:
    async def test_delete_removes_db_rows(
        self, store: SqliteKnowledgeStore
    ) -> None:
        await _seed_document(store)
        service = DocumentsService(knowledge_store=store)

        await service.delete_document("doc1")

        assert await store.get_document_metadata("doc1") is None

    async def test_delete_missing_raises_not_found(
        self, store: SqliteKnowledgeStore
    ) -> None:
        service = DocumentsService(knowledge_store=store)

        with pytest.raises(NotFoundError):
            await service.delete_document("missing")
