"""FTS5 MATCH query builder.

Converts a list of expanded query terms into a safe SQLite FTS5 MATCH string.
Raw user input must never be passed to KnowledgeStore directly — always go
through build_fts_match() first.
"""

from __future__ import annotations

import re

from pipelines.retrieval.config import RetrievalConfig

# Matches terms that consist entirely of Cyrillic characters.
_CYRILLIC_RE = re.compile(r"^[\u0400-\u04FF]+$")

# FTS5 characters that require the term to be wrapped in double quotes.
_FTS5_SPECIAL = frozenset('" ()-*^\t\n')


def sanitize_fts_term(term: str) -> str:
    """Escape FTS5 special characters in a single term.

    If the term contains any FTS5 special character or whitespace, wraps it in
    double quotes and escapes internal double quotes by doubling them.
    Returns an empty string unchanged.
    """
    if not term:
        return ""
    if any(ch in _FTS5_SPECIAL for ch in term):
        escaped = term.replace('"', '""')
        return f'"{escaped}"'
    return term


def build_fts_match(terms: list[str], config: RetrievalConfig) -> str:
    """Build a safe FTS5 MATCH string from expanded query terms.

    Rules:
    - Each term is sanitized (FTS5 special chars → quoted phrase).
    - A purely Cyrillic term with len >= config.prefix_min_len gets a trailing
      wildcard (*) when config.enable_prefixes is True.
    - All terms are joined with OR.
    - Returns empty string if terms is empty or contains only empty strings.

    The caller must guard against an empty result before passing to store.
    """
    if not terms:
        return ""
    parts: list[str] = []
    for term in terms:
        if not term:
            continue
        sanitized = sanitize_fts_term(term)
        if (
            config.enable_prefixes
            and len(term) >= config.prefix_min_len
            and bool(_CYRILLIC_RE.match(term))
        ):
            sanitized = sanitized + "*"
        parts.append(sanitized)
    return " OR ".join(parts)
