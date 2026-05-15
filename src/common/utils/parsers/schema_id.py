import re
from typing import NamedTuple

# Compiled regex for Target Schema ID line recognition
# Pattern: "Target Schema ID:" with flexible whitespace and case-insensitive
# Captures: ([a-z_][a-z0-9_-]*)
SCHEMA_ID_PATTERN = re.compile(
    r"target\s+schema\s+id\s*:\s*([a-z_][a-z0-9_-]*)",
    re.IGNORECASE
)


class SchemaIDMatch(NamedTuple):
    """Result of finding Target Schema ID in document lines"""
    schema_id: str
    line_number: int


def find_schema_id(lines: list[str], search_limit: int | None = None) -> SchemaIDMatch | None:
    """Search for Target Schema ID marker in document lines.

    Scans the first N lines (or all lines if search_limit is None) looking for the
    Target Schema ID pattern and returns the canonical schema ID and its line number.

    Args:
        lines: List of document lines
        search_limit: Maximum number of lines to search. Defaults to all lines.

    Returns:
        SchemaIDMatch with schema_id (canonical, lowercase) and line_number (0-indexed),
        or None if not found.

    Examples:
        >>> result = find_schema_id(["Target Schema ID: diagnostic", "# Heading"])
        >>> result.schema_id
        'diagnostic'
        >>> result.line_number
        0
    """
    limit = min(search_limit or len(lines), len(lines))
    for i in range(limit):
        match = SCHEMA_ID_PATTERN.search(lines[i])
        if match:
            schema_id = match.group(1).strip().lower()
            return SchemaIDMatch(schema_id=schema_id, line_number=i)
    return None
