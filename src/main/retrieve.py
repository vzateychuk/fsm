#!/usr/bin/env python3
"""Runner for retrieval pipeline debug."""

import asyncio
import json
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from common import setup_logging
from pipelines.retrieval.runner import RetrievalRunner
from pipelines.retrieval.models import RetrieveRequest
from pipelines.retrieval.config import RetrievalConfig
from store.sql.sqlite_knowledge_store import SqliteKnowledgeStore


async def main():
    """Run retrieval query with debug output."""
    setup_logging(level=logging.DEBUG, log_file=None)
    logger = logging.getLogger(__name__)

    db_path = os.getenv("DB_PATH", ".data/db/ingest.db")
    query = sys.argv[1] if len(sys.argv) > 1 else "анализ"
    category = sys.argv[2] if len(sys.argv) > 2 else None

    # Load config from YAML
    config = RetrievalConfig.load(Path("config/retrieve.yaml"))
    store = SqliteKnowledgeStore(db_path=db_path, bm25_weights=config.bm25_weights)

    runner = RetrievalRunner(store=store, config=config)

    request = RetrieveRequest(query=query, category=category)
    logger.info(f"Query: {query!r}, Category: {category}")

    response = await runner.run(request)

    print(f"\n{'='*60}")
    print(f"QUERY: {request.query}")
    print(f"NORMALIZED: {response.query_normalized}")
    print(f"FTS MATCH: {response.fts_match}")
    print(f"DOCUMENTS FOUND: {len(response.documents)}")
    print(f"CHUNKS FOUND: {len(response.chunks)}")
    print(f"{'='*60}\n")

    for doc in response.documents:
        print(f"Document: {doc.document_id}")
        print(f"  Category: {doc.category}")
        print(f"  Source: {doc.source_path}")
        print(f"  Chunks: {len(doc.chunks)}")
        for chunk in doc.chunks:
            print(f"    - [{chunk.kind}] {chunk.heading or chunk.text[:50]}...")

if __name__ == "__main__":
    asyncio.run(main())
