"""Shared text normalizer: NFKC + lowercase + ё→е.

Used by the ingest pipeline (document preprocessing) and the retrieval
pipeline (query normalization) to ensure identical surface forms.
"""

from __future__ import annotations

import re
import unicodedata

# Pattern to match punctuation and split by it
_PUNCTUATION_RE = re.compile(r'[^\w\s]', flags=re.UNICODE)


def normalize_text(text: str) -> str:
    """Apply NFKC normalization, convert to lowercase, and replace ё with е."""
    text = unicodedata.normalize("NFKC", text)
    text = text.lower()
    return text.replace("ё", "е")


def tokenize_query(text: str) -> list[str]:
    """Split query text into tokens, removing punctuation and pure digits.

    Process:
    1. Remove punctuation
    2. Split by whitespace
    3. Filter out empty tokens and pure numeric tokens

    Pure numeric tokens (e.g., "37", "8") are filtered because they are
    contextual values (temperatures, lab results) rather than search terms.
    Only tokens with at least one letter are kept.

    Example:
        "болит живот справа, температура 37.8" →
        ["болит", "живот", "справа", "температура"]
    """
    # Remove punctuation: keep only word characters and spaces
    # \w matches letters, digits, underscore in Unicode mode
    text = _PUNCTUATION_RE.sub(' ', text)

    # Split by whitespace and filter:
    # - empty tokens
    # - pure numeric tokens (no letters)
    tokens = [
        token for token in text.split()
        if token and not token.isdigit()
    ]

    return tokens
