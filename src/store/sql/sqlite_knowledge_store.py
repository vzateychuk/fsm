from __future__ import annotations

import hashlib
from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import aiosqlite

from store.knowledge_store import Category, ChunkKind, ChunkSearchResult, DocumentMetadata

if TYPE_CHECKING:
    from pipelines.ingest.models import ChunkTagged


def _chunk_id(document_id: str, section_path: str | None, kind: str, text: str) -> str:
    raw = f"{document_id}|{section_path or ''}|{kind}|{text}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


@dataclass(slots=True)
class SqliteKnowledgeStore:
    db_path: str
    bm25_weights: tuple[float, float, float, float] = (1.0, 2.5, 2.0, 3.5)

    async def save_document(
        self,
        *,
        document_id: str,
        source_path: str,
        source_sha256: str,
        category: Category,
        indexed_at: str,
        document_date: str,
        raw_text: str,
    ) -> None:
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute(
                "INSERT OR REPLACE INTO documents (id, source_path, source_sha256, category, indexed_at, document_date, raw_text)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (document_id, source_path, source_sha256, category, indexed_at, document_date, raw_text),
            )
            await conn.commit()

    async def replace_document_chunks(
        self,
        *,
        document_id: str,
        chunks: list[ChunkTagged],
    ) -> list[str]:
        rows = [
            (
                _chunk_id(document_id, chunk.get("section_path"), chunk["kind"], chunk["text"]),
                document_id,
                i,
                chunk.get("section_path"),
                chunk.get("heading"),
                chunk["kind"],
                chunk["text"],
                chunk.get("tags_text"),
            )
            for i, chunk in enumerate(chunks)
        ]
        chunk_ids = [row[0] for row in rows]

        async with aiosqlite.connect(self.db_path) as conn:
            try:
                # 1. FTS delete: log old entries with column values before removing source rows
                await conn.execute(
                    "INSERT INTO chunks_fts(chunks_fts, rowid, text, heading, section_path, tags_text)"
                    " SELECT 'delete', c.chunk_pk, c.text, c.heading, c.section_path, c.tags_text"
                    " FROM chunks c WHERE c.document_id = ?",
                    (document_id,),
                )
                # 2. Delete old chunks
                await conn.execute("DELETE FROM chunks WHERE document_id = ?", (document_id,))

                # 3. Batch insert new chunks
                await conn.executemany(
                    "INSERT INTO chunks"
                    " (chunk_id, document_id, chunk_no, section_path, heading, kind, text, tags_text)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    rows,
                )

                # 4. Rebuild FTS from new chunks
                await conn.execute(
                    "INSERT INTO chunks_fts(rowid, text, heading, section_path, tags_text)"
                    " SELECT chunk_pk, text, heading, section_path, tags_text"
                    " FROM chunks WHERE document_id = ?",
                    (document_id,),
                )
                await conn.commit()
            except Exception:
                await conn.rollback()
                raise

        return chunk_ids

    async def get_documents_raw_text(
        self,
        document_ids: list[str],
    ) -> dict[str, str]:
        if not document_ids:
            return {}
        placeholders = ",".join("?" * len(document_ids))
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            async with conn.execute(
                f"SELECT id, raw_text FROM documents WHERE id IN ({placeholders})",
                document_ids,
            ) as cursor:
                rows = await cursor.fetchall()
        return {row["id"]: row["raw_text"] for row in rows}

    async def get_neighbor_chunks(
        self,
        document_id: str,
        chunk_no: int,
        window: int,
    ) -> list[ChunkSearchResult]:
        lo = chunk_no - window
        hi = chunk_no + window
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            async with conn.execute(
                "SELECT c.chunk_id, c.document_id, c.chunk_no, c.kind, c.text,"
                " c.section_path, c.heading, c.tags_text,"
                " d.source_path, d.category, d.document_date"
                " FROM chunks c"
                " JOIN documents d ON c.document_id = d.id"
                " WHERE c.document_id = ? AND c.chunk_no BETWEEN ? AND ?"
                " ORDER BY c.chunk_no",
                (document_id, lo, hi),
            ) as cursor:
                rows = await cursor.fetchall()
        return [
            ChunkSearchResult(
                chunk_id=row["chunk_id"],
                document_id=row["document_id"],
                chunk_no=row["chunk_no"],
                kind=row["kind"],
                text=row["text"],
                section_path=row["section_path"],
                heading=row["heading"],
                tags_text=row["tags_text"],
                source_path=row["source_path"],
                category=row["category"],
                document_date=row["document_date"],
                rank=0.0,
            )
            for row in rows
        ]

    async def search_chunks(
        self,
        query: str,
        *,
        category: Category | None = None,
        document_id: str | None = None,
        kinds: set[ChunkKind] | None = None,
        section_path_prefix: str | None = None,
        limit: int = 20,
        limit_per_document: int = 3,
        prelimit: int = 200,
        bm25_weights: tuple[float, float, float, float] | None = None,
        meta_score_factor: float = 0.1,
    ) -> list[ChunkSearchResult]:
        weights = bm25_weights if bm25_weights is not None else self.bm25_weights
        sql = (
            "SELECT c.chunk_id, c.document_id, c.chunk_no, c.kind, c.text,"
            " c.section_path, c.heading, c.tags_text,"
            " d.source_path, d.category, d.document_date, bm25(chunks_fts, ?, ?, ?, ?) AS rank"
            " FROM chunks_fts"
            " JOIN chunks c ON chunks_fts.rowid = c.chunk_pk"
            " JOIN documents d ON c.document_id = d.id"
            " WHERE chunks_fts MATCH ?"
        )
        params: list[Any] = [*weights, query]

        if category:
            sql += " AND d.category = ?"
            params.append(category)
        if document_id:
            sql += " AND c.document_id = ?"
            params.append(document_id)
        if kinds:
            placeholders = ",".join("?" * len(kinds))
            sql += f" AND c.kind IN ({placeholders})"
            params.extend(sorted(kinds))
        if section_path_prefix:
            sql += " AND c.section_path LIKE ?"
            params.append(f"{section_path_prefix}%")

        sql += " ORDER BY rank LIMIT ?"
        params.append(prelimit)

        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            async with conn.execute(sql, params) as cursor:
                rows = await cursor.fetchall()

        # Apply meta_score_factor penalty to administrative chunks before diversity filtering.
        # BM25 scores are negative (more negative = more relevant).
        # Multiplying by a small factor (e.g., 0.1) makes the score less negative = lower priority.
        if meta_score_factor < 1.0:
            rows = [dict(row) for row in rows]  # Convert sqlite3.Row to mutable dicts
            for row in rows:
                if row["kind"] == "meta":
                    row["rank"] = row["rank"] * meta_score_factor
            # Re-sort by penalized rank
            rows.sort(key=lambda r: r["rank"])

        diversity_enabled = limit_per_document > 0
        counts_per_doc: dict[str, int] = defaultdict(int)
        results: list[ChunkSearchResult] = []
        for row in rows:
            doc_id = row["document_id"]
            if diversity_enabled and counts_per_doc[doc_id] >= limit_per_document:
                continue
            counts_per_doc[doc_id] += 1
            results.append(
                ChunkSearchResult(
                    chunk_id=row["chunk_id"],
                    document_id=doc_id,
                    chunk_no=row["chunk_no"],
                    kind=row["kind"],
                    text=row["text"],
                    section_path=row["section_path"],
                    heading=row["heading"],
                    tags_text=row["tags_text"],
                    source_path=row["source_path"],
                    category=row["category"],
                    document_date=row["document_date"],
                    rank=row["rank"],
                )
            )
            if len(results) >= limit:
                break

        return results

    async def list_documents_by_date(
        self,
        *,
        limit: int = 5,
        category: Category | None = None,
    ) -> list[DocumentMetadata]:
        query = (
            "SELECT id, source_path, category, document_date, indexed_at"
            " FROM documents"
        )
        params: list[Any] = []

        if category:
            query += " WHERE category = ?"
            params.append(category)

        query += " ORDER BY COALESCE(document_date, indexed_at) DESC LIMIT ?"
        params.append(limit)

        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            async with conn.execute(query, params) as cursor:
                rows = await cursor.fetchall()

        return [
            DocumentMetadata(
                document_id=row["id"],
                source_path=row["source_path"],
                category=row["category"],
                document_date=row["document_date"],
                indexed_at=row["indexed_at"],
            )
            for row in rows
        ]

    async def get_document_chunks(
        self,
        document_id: str,
        limit: int,
    ) -> list[ChunkSearchResult]:
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            async with conn.execute(
                "SELECT c.chunk_id, c.document_id, c.chunk_no, c.kind, c.text,"
                " c.section_path, c.heading, c.tags_text,"
                " d.source_path, d.category, d.document_date"
                " FROM chunks c"
                " JOIN documents d ON c.document_id = d.id"
                " WHERE c.document_id = ?"
                " ORDER BY c.chunk_no ASC"
                " LIMIT ?",
                (document_id, limit),
            ) as cursor:
                rows = await cursor.fetchall()

        return [
            ChunkSearchResult(
                chunk_id=row["chunk_id"],
                document_id=row["document_id"],
                chunk_no=row["chunk_no"],
                kind=row["kind"],
                text=row["text"],
                section_path=row["section_path"],
                heading=row["heading"],
                tags_text=row["tags_text"],
                source_path=row["source_path"],
                category=row["category"],
                document_date=row["document_date"],
                rank=0.0,
            )
            for row in rows
        ]
