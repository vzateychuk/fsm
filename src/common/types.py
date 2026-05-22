"""Shared domain types used across ingest, store, and retrieval layers."""

from typing import Literal

ChunkKind = Literal["section", "table", "list", "fact", "meta"]
