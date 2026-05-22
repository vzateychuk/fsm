"""Test fixtures for retrieval verification.

Use these fixtures to test that retrieval finds relevant documents
for the query: "болит живот справа, температура 37.8"
"""

import tempfile
from pathlib import Path

import aiosqlite
import pytest


@pytest.fixture
async def test_db_with_medical_docs() -> str:
    """Create test database with 3 medical documents for abdominal pain query."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test_medical.db")

        async with aiosqlite.connect(db_path) as conn:
            schema_path = Path("src/store/sql/schema.sql")
            schema = schema_path.read_text()
            for stmt in schema.split(";"):
                if stmt.strip():
                    await conn.execute(stmt)
            await conn.commit()

        # Insert 3 medical documents with relevant content
        async with aiosqlite.connect(db_path) as conn:
            # Document 1: Appendicitis (HIGH relevance)
            # Exact matches: "боль", "живот", "справа", "температура"
            await conn.execute(
                "INSERT INTO documents (id, source_path, source_sha256, category, indexed_at, document_date, raw_text)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    "doc_appendicitis",
                    "appendicitis_case.md",
                    "sha256_appendicitis",
                    "Диагноз",
                    "2026-05-20T00:00:00",
                    "2026-05-20",
                    "Острый аппендицит. Пациент жалуется на острую боль в животе справа. "
                    "При пальпации резкая болезненность в правой подвздошной области. "
                    "Температура тела 38.5°C. УЗИ: утолщение стенки аппендикса до 8 мм.",
                ),
            )

            # Document 2: Gastroenteritis (MEDIUM relevance)
            # Contains synonyms: "болевой синдром", "абдомен", "fever", "повышена"
            await conn.execute(
                "INSERT INTO documents (id, source_path, source_sha256, category, indexed_at, document_date, raw_text)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    "doc_gastroenteritis",
                    "gastroenteritis_case.md",
                    "sha256_gastroenteritis",
                    "Диагноз",
                    "2026-05-19T00:00:00",
                    "2026-05-19",
                    "Острый гастроэнтерит. Болевой синдром в области абдомена. "
                    "Боль усиливается с правой стороны. Fever 37.8. "
                    "Рвота и диарея. Назначена регидратация.",
                ),
            )

            # Document 3: Ovarian cyst (LOWER relevance)
            # Contains: "боль справа", "живот", "температура повышена"
            # But in different context (gynecology)
            await conn.execute(
                "INSERT INTO documents (id, source_path, source_sha256, category, indexed_at, document_date, raw_text)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    "doc_ovarian_cyst",
                    "gynecology_ultrasound.md",
                    "sha256_ovarian_cyst",
                    "Исследование",
                    "2026-05-18T00:00:00",
                    "2026-05-18",
                    "УЗИ органов малого таза. В правом яичнике киста размером 3 см. "
                    "Пациентка испытывает боль в животе справа. Температура тела повышена до 37.2°C. "
                    "Рекомендовано повторное УЗИ через 3 месяца.",
                ),
            )

            # Add chunks for each document
            # Doc 1 chunks
            for i, chunk_text in enumerate([
                "Острый аппендицит. Пациент жалуется на острую боль в животе справа.",
                "При пальпации резкая болезненность в правой подвздошной области.",
                "Температура тела 38.5°C. УЗИ: утолщение стенки аппендикса до 8 мм.",
            ]):
                await conn.execute(
                    "INSERT INTO chunks (chunk_id, document_id, chunk_no, kind, text, section_path, heading, tags_text)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (f"doc1_chunk{i}", "doc_appendicitis", i, "fact", chunk_text, None, None, None),
                )

            # Doc 2 chunks
            for i, chunk_text in enumerate([
                "Острый гастроэнтерит. Болевой синдром в области абдомена.",
                "Боль усиливается с правой стороны. Fever 37.8.",
                "Рвота и диарея. Назначена регидратация.",
            ]):
                await conn.execute(
                    "INSERT INTO chunks (chunk_id, document_id, chunk_no, kind, text, section_path, heading, tags_text)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (f"doc2_chunk{i}", "doc_gastroenteritis", i, "fact", chunk_text, None, None, None),
                )

            # Doc 3 chunks
            for i, chunk_text in enumerate([
                "УЗИ органов малого таза. В правом яичнике киста размером 3 см.",
                "Пациентка испытывает боль в животе справа.",
                "Температура тела повышена до 37.2°C.",
            ]):
                await conn.execute(
                    "INSERT INTO chunks (chunk_id, document_id, chunk_no, kind, text, section_path, heading, tags_text)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (f"doc3_chunk{i}", "doc_ovarian_cyst", i, "fact", chunk_text, None, None, None),
                )

            await conn.commit()

        yield db_path


# Document descriptions for reference:
"""
FIXTURE 1: doc_appendicitis (HIGH relevance)
- Category: Диагноз
- Content: Classic appendicitis case
- Query term matches:
  * "болит" → "боль" (exact form)
  * "живот" → "животе" (inflected form of живот)
  * "справа" → "справа" (exact match)
  * "температура" → "Температура" (exact match + numeric value 38.5)
- Expected BM25 rank: HIGHEST
- Best chunk: "Пациент жалуется на острую боль в животе справа."

FIXTURE 2: doc_gastroenteritis (MEDIUM relevance)
- Category: Диагноз
- Content: Acute gastroenteritis with fever
- Query term matches:
  * "болит" → "Болевой" (different form) + "Боль" (exact form)
  * "живот" → "абдомена" (synonym, area of abdomen)
  * "справа" → "правой стороны" (synonym for right side)
  * "температура" → "Fever" (English synonym) + "37.8" (numeric match)
- Expected BM25 rank: MEDIUM
- Best chunk: "Боль усиливается с правой стороны. Fever 37.8."

FIXTURE 3: doc_ovarian_cyst (LOWER relevance)
- Category: Исследование (different category)
- Content: Gynecology ultrasound with ovarian cyst
- Query term matches:
  * "болит" → "боль" (exact match but in different context)
  * "живот" → "животе" (exact match)
  * "справа" → "справа" (exact match)
  * "температура" → "Температура" (exact match but lower value 37.2)
- Expected BM25 rank: LOWER
- Best chunk: "Пациентка испытывает боль в животе справа."

Usage in tests:
    @pytest.mark.asyncio
    async def test_retrieval_abdominal_pain(test_db_with_medical_docs):
        db_path = test_db_with_medical_docs
        store = SqliteKnowledgeStore(db_path=db_path)
        
        # Should find all 3 documents, ranked by relevance
        results = await store.search_chunks(
            query="болит живот справа температура",
            limit=20,
            prelimit=200,
        )
        
        # Verify results
        assert len(results) >= 3
        doc_ids = [r.document_id for r in results]
        assert "doc_appendicitis" in doc_ids
        assert "doc_gastroenteritis" in doc_ids
        assert "doc_ovarian_cyst" in doc_ids
"""


# Integration test example
@pytest.mark.asyncio
async def test_retrieval_abdominal_pain(test_db_with_medical_docs: str) -> None:
    """Test that retrieval finds and ranks medical documents for abdominal pain query.
    
    Query: "болит живот справа, температура 37.8"
    After tokenization: ["болит", "живот", "справа", "температура"]
    
    Expected results:
    1. doc_appendicitis (HIGH) - exact matches for all terms
    2. doc_gastroenteritis (MEDIUM) - synonyms + fever/temperature
    3. doc_ovarian_cyst (LOWER) - matches but gynecology context
    """
    from src.store.sql.sqlite_knowledge_store import SqliteKnowledgeStore
    from src.pipelines.retrieval.config import RetrievalConfig

    config = RetrievalConfig(
        prelimit=200,
        bm25_weights=(1.0, 2.5, 2.0, 3.5),
        enable_prefixes=True,
        prefix_min_len=5,
        category_mode="soft",
    )
    store = SqliteKnowledgeStore(db_path=test_db_with_medical_docs, bm25_weights=config.bm25_weights)

    # Query after normalization and tokenization
    # Original: "болит живот справа, температура 37.8"
    # After tokenize: "болит живот справа температура" (no punctuation, no digits)
    results = await store.search_chunks(
        query="болит живот справа температура",
        limit=20,
        prelimit=200,
        bm25_weights=config.bm25_weights,
    )

    # Should find all 3 documents
    assert len(results) >= 3, f"Expected at least 3 results, got {len(results)}"

    # Extract unique document IDs preserving order (by BM25 rank)
    doc_ids = [r.document_id for r in results]
    unique_doc_ids = []
    for doc_id in doc_ids:
        if doc_id not in unique_doc_ids:
            unique_doc_ids.append(doc_id)

    # All 3 documents should be found
    assert "doc_appendicitis" in unique_doc_ids
    assert "doc_gastroenteritis" in unique_doc_ids
    assert "doc_ovarian_cyst" in unique_doc_ids

    # Appendicitis should rank highest (most relevant)
    assert unique_doc_ids[0] == "doc_appendicitis", (
        f"Expected doc_appendicitis to rank first, but got: {unique_doc_ids}"
    )

    # Print results for manual inspection
    print(f"\nRetrieval results for query: 'болит живот справа, температура 37.8'")
    print(f"Found {len(results)} chunks from {len(unique_doc_ids)} unique documents\n")
    for i, result in enumerate(results[:5], 1):
        print(f"{i}. [{result.document_id}] Rank={result.rank:.4f}")
        print(f"   Text: {result.text[:60]}...\n")
