import re
from pathlib import Path
from typing import NamedTuple

import yaml  # type: ignore[import-untyped]

# Compiled regex for Категория line recognition.
# Works on already-lowercased text (after S1 PreprocessText).
# Accepts colon inside or outside bold: **категория:** or **категория**:
_CATEGORY_PATTERN = re.compile(r"\*\*категория:?\*\*:?\s*(.+)")


class SchemaIDMatch(NamedTuple):
    """Result of finding Категория marker in document lines."""
    category: str
    line_number: int


def load_categories(config_path: Path) -> list[str]:
    """Load allowed category list from YAML config file.

    Args:
        config_path: Path to categories.yaml

    Returns:
        List of canonical category strings as defined in the config.

    Raises:
        FileNotFoundError: if config file does not exist
        KeyError: if "categories" key is missing
    """
    with config_path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return list(data["categories"])


def find_category(
    lines: list[str],
    allowed_categories: list[str],
    search_limit: int | None = None,
) -> SchemaIDMatch | None:
    """Search for **Категория:** marker in document lines.

    Scans the first N lines (or all lines if search_limit is None) looking for
    the category pattern. Matches by first word (prefix matching): e.g.,
    "Исследование (УЗИ/МРТ/КТ)" matches config entry "Исследование".

    Args:
        lines: List of document lines (already lowercased after S1)
        allowed_categories: List of canonical category strings from config
        search_limit: Maximum number of lines to search. Defaults to all lines.

    Returns:
        SchemaIDMatch with canonical category and line_number (0-indexed),
        or None if not found or first word not in allowed_categories.

    Examples:
        >>> result = find_category(["**категория:** консультация"], ["Консультация"])
        >>> result.category
        'Консультация'
        >>> result.line_number
        0
        >>> result = find_category(["**категория:** исследование (узи/мрт/кт)"], ["Исследование"])
        >>> result.category
        'Исследование'
    """
    allowed_by_first_word = {cat.split()[0].lower(): cat for cat in allowed_categories}
    limit = min(search_limit or len(lines), len(lines))
    for i in range(limit):
        m = _CATEGORY_PATTERN.search(lines[i])
        if m:
            found = m.group(1).strip()
            first_word = found.split()[0].lower()
            canonical = allowed_by_first_word.get(first_word)
            if canonical is not None:
                return SchemaIDMatch(category=canonical, line_number=i)
    return None
