"""Alias map for retrieval query expansion.

Re-exports ALIAS_MAP from common package so both ingest (tagging)
and retrieval (ExpandAliases step) use the same canonical dictionary.
"""

from common.alias_map import ALIAS_MAP

__all__ = ["ALIAS_MAP"]
