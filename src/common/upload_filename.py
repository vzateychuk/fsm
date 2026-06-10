"""Sanitize uploaded file names for storage and logging."""

from __future__ import annotations

from pathlib import Path

_DEFAULT_FILENAME = "upload.md"


def sanitize_upload_filename(name: str | None) -> str:
    """Return basename only; fallback upload.md; strip null bytes."""
    raw = (name or "").strip() or _DEFAULT_FILENAME
    basename = Path(raw.replace("\0", "")).name
    return basename or _DEFAULT_FILENAME
