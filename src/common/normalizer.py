"""Shared text normalizer: NFKC + lowercase + ё→е.

Used by the ingest pipeline (document preprocessing) and the retrieval
pipeline (query normalization) to ensure identical surface forms.
"""

from __future__ import annotations

import unicodedata


def normalize_text(text: str) -> str:
    """Apply NFKC normalization, convert to lowercase, and replace ё with е."""
    text = unicodedata.normalize("NFKC", text)
    text = text.lower()
    return text.replace("ё", "е")
