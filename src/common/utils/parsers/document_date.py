"""Extract document date from markdown content markers or YAML metadata.

Priority order (first non-None wins):
1. Content markers: lines like '**Дата:** 2023-02-24' or '**Дата исследования:** 05.06.2025'
   Supports multiple formats and markup styles (see supported_formats below).
   Excludes: 'Дата рождения' (birth date), 'Дата валидации' (validation timestamp),
   'Дата заказа' (test order date), 'Дата отправки' (send date), 'Дата печати' (print date).
2. YAML metadata block: --- date: 2023-02-24 ---

Supported content marker formats:
  - Markup: **bold** or *italic*
  - Date formats: YYYY-MM-DD (ISO), DD.MM.YYYY (Russian), DD/MM/YYYY (slashes)
  - Optional time component: DD.MM.YYYY HH:MM (time stripped, date only extracted)
  - Optional colon separator: **Дата:** or **Дата** both work
  - Optional whitespace: ** Дата ** or **Дата** both work

Example valid lines:
  - **Дата исследования:** 15.03.2024
  - *Дата анализа* 15/03/2024
  - **Дата и время:** 2024-03-15 10:30
  - **Дата выписки:** 15.03.2024 14:25

Note: filename-based extraction is intentionally NOT supported, since filenames
may contain arbitrary dates unrelated to the document's actual date.

Output is always normalized to ISO YYYY-MM-DD or None.
"""
from __future__ import annotations

import re
from datetime import date

import yaml

# Markdown content marker: **Дата[suffix]**: <date> or *Дата[suffix]*: <date>
# Supports both bold (**) and italic (*) markup.
# Captures suffix (e.g. ' исследования', ' рождения') for blacklist filtering.
# Supports date formats:
#   - YYYY-MM-DD (ISO)
#   - DD.MM.YYYY (Russian with dots)
#   - DD.MM.YYYY HH:MM (with time, time is ignored)
#   - DD/MM/YYYY (with slashes)
#   - DD/MM/YYYY HH:MM (with slashes and time, time is ignored)
_CONTENT_DATE_RE = re.compile(
    r"[\*]{1,2}\s*Дата(?P<suffix>[^\*]*?)[\*]{1,2}\s*:?\s*(?P<date>\d{4}-\d{2}-\d{2}|\d{2}[./]\d{2}[./]\d{4}(?:\s+\d{2}:\d{2})?)",
    re.IGNORECASE,
)

# Suffixes that mark dates which are NOT the document date.
# Includes: birth date, validation date, order date (for tests/procedures), send date, print date.
_EXCLUDED_SUFFIXES = ("рождения", "валидации", "заказа", "отправки", "печати")

# Lines from top of file to scan for content markers (header section).
_CONTENT_SCAN_LIMIT = 30


def _normalize_date(date_str: str) -> str:
    """Normalize various date formats to YYYY-MM-DD.

    Handles:
    - YYYY-MM-DD (ISO) → unchanged
    - DD.MM.YYYY (Russian with dots) → YYYY-MM-DD
    - DD/MM/YYYY (with slashes) → YYYY-MM-DD
    - DD.MM.YYYY HH:MM (with time) → YYYY-MM-DD (time stripped)
    - DD/MM/YYYY HH:MM (slashes + time) → YYYY-MM-DD (time stripped)
    """
    # Strip time component if present (e.g., "01.03.2024 10:30" -> "01.03.2024")
    date_part = date_str.split()[0]

    # Handle DD.MM.YYYY or DD/MM/YYYY formats
    if "." in date_part or "/" in date_part:
        separator = "." if "." in date_part else "/"
        parts = date_part.split(separator)
        if len(parts) == 3:
            day, month, year = parts
            # Ensure 4-digit year (handle both YYYY and YY)
            if len(year) == 2:
                year = "20" + year  # Assume 20xx for 2-digit years
            return f"{year}-{month:0>2}-{day:0>2}"

    # Already in YYYY-MM-DD format or unknown format -> return as is
    return date_part


def _extract_from_content(content: str) -> str | None:
    """Extract date from markdown content header (first 30 lines).

    Accepts: '**Дата:**', '**Дата исследования:**', '**Дата приема:**', etc.
    Rejects: '**Дата рождения:**', '**Дата валидации:**'.
    """
    lines = content.split("\n")[:_CONTENT_SCAN_LIMIT]
    for line in lines:
        for match in _CONTENT_DATE_RE.finditer(line):
            suffix = match.group("suffix").strip().lower()
            if any(excl in suffix for excl in _EXCLUDED_SUFFIXES):
                continue
            return _normalize_date(match.group("date"))
    return None


def _extract_from_yaml_metadata(content: str) -> str | None:
    """Extract date from YAML metadata block (--- ... ---) at top of file.

    Keys checked (first non-empty wins): date, document_date, visit_date.
    """
    lines = content.split("\n")
    if not lines or lines[0].strip() != "---":
        return None

    yaml_end: int | None = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            yaml_end = i
            break
    if yaml_end is None:
        return None

    yaml_text = "\n".join(lines[1:yaml_end])
    try:
        metadata = yaml.safe_load(yaml_text) or {}
    except Exception:
        return None
    if not isinstance(metadata, dict):
        return None

    date_val = metadata.get("date") or metadata.get("document_date") or metadata.get("visit_date")
    if date_val is None:
        return None
    if isinstance(date_val, date):
        return date_val.isoformat()
    return _normalize_date(str(date_val))


def extract_document_date(content: str) -> str | None:
    """Extract document date with priority: content marker > YAML metadata.

    Returns ISO format YYYY-MM-DD or None if no date could be extracted.

    Args:
        content: raw markdown content (used for header markers and YAML metadata)
    """
    return _extract_from_content(content) or _extract_from_yaml_metadata(content)
