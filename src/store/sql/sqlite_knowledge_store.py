from __future__ import annotations

import hashlib
from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import aiosqlite

from store.knowledge_store import ChunkKind, ChunkSearchResult, DocType

if TYPE_CHECKING:
    from pipelines.ingest.models import ChunkTagged


_BM25_WEIGHTS = (1.0, 2.5, 2.0, 3.5)


def _chunk_id(document_id: str, section_path: str | None, kind: str, text: str) -> str:
    raw = f"{document_id}|{section_path or ''}|{kind}|{text}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


@dataclass(slots=True)
class SqliteKnowledgeStore:
    db_path: str

    async def save_document(
        self,
        *,
        document_id: str,
        source_path: str,
        source_sha256: str,
        doc_type: DocType,
        indexed_at: str,
        raw_text: str,
    ) -> None:
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute(
                "INSERT OR REPLACE INTO documents (id, source_path, source_sha256, doc_type, indexed_at, raw_text)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (document_id, source_path, source_sha256, doc_type, indexed_at, raw_text),
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
                # 1. FTS delete: log old entries before removing source rows
                await conn.execute(
                    "INSERT INTO chunks_fts(chunks_fts, rowid)"
                    " SELECT 'delete', c.chunk_pk FROM chunks c WHERE c.document_id = ?",
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

    async def search_chunks(
        self,
        query: str,
        *,
        doc_type: DocType | None = None,
        document_id: str | None = None,
        kinds: set[ChunkKind] | None = None,
        section_path_prefix: str | None = None,
        limit: int = 20,
        limit_per_document: int = 3,
        prelimit: int = 200,
    ) -> list[ChunkSearchResult]:
        sql = (
            "SELECT c.chunk_id, c.document_id, c.chunk_no, c.kind, c.text,"
            " c.section_path, c.heading, c.tags_text,"
            " d.source_path, d.doc_type, bm25(chunks_fts, ?, ?, ?, ?) AS rank"
            " FROM chunks_fts"
            " JOIN chunks c ON chunks_fts.rowid = c.chunk_pk"
            " JOIN documents d ON c.document_id = d.id"
            " WHERE chunks_fts MATCH ?"
        )
        params: list[Any] = [*_BM25_WEIGHTS, query]

        if doc_type:
            sql += " AND d.doc_type = ?"
            params.append(doc_type)
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
                    doc_type=row["doc_type"],
                    rank=row["rank"],
                )
            )
            if len(results) >= limit:
                break

        return results
