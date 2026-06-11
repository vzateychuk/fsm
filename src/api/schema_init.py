"""Database schema initialization (user + system DBs)."""

from __future__ import annotations

import logging
from pathlib import Path

import aiosqlite

from src.api.user_db_paths import default_system_db_path, ensure_db_parent

logger = logging.getLogger(__name__)

SYSTEM_SCHEMA_PATH = Path(__file__).parent.parent / "store" / "sql" / "system_schema.sql"
USER_SCHEMA_PATH = Path(__file__).parent.parent / "store" / "sql" / "schema.sql"


async def ensure_schema(db_path: str) -> None:
    """Initialize user database schema (idempotent)."""
    schema = USER_SCHEMA_PATH.read_text(encoding="utf-8")
    ensure_db_parent(db_path)
    async with aiosqlite.connect(db_path) as conn:
        await conn.executescript(schema)
    logger.info("User schema initialized: db=%s", db_path)


async def ensure_system_schema(db_path: str | None = None) -> None:
    """Initialize system database schema (idempotent)."""
    path = db_path or default_system_db_path()
    schema = SYSTEM_SCHEMA_PATH.read_text(encoding="utf-8")
    ensure_db_parent(path)
    async with aiosqlite.connect(path) as conn:
        await conn.executescript(schema)
    logger.info("System schema initialized: db=%s", path)
