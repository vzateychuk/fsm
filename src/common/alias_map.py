"""Medical terminology alias mappings and utility functions.

Canonical location for ALIAS_MAP used by both ingest (tagging) and retrieval
(ExpandAliases step). Loads configuration from config/aliases.yaml at application startup.
"""

import re
from pathlib import Path

import yaml


def _load_config(config_dir: str = "config") -> dict:
    """Load aliases configuration from YAML file.

    Args:
        config_dir: Directory containing aliases.yaml (relative to project root)

    Returns:
        Parsed YAML configuration dict with 'aliases', 'stopwords', 'units_exact', 'units_regex'
    """
    # Support both relative paths (from project root) and absolute paths
    config_path = Path(config_dir) / "aliases.yaml"

    if not config_path.exists():
        # Try looking up from src/ subdirectory
        config_path = Path(__file__).parent.parent.parent / config_dir / "aliases.yaml"

    if not config_path.exists():
        raise FileNotFoundError(
            f"Configuration file not found: {config_path}\n"
            f"Expected location: config/aliases.yaml (relative to project root)"
        )

    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _initialize_config():
    """Initialize configuration from YAML file."""
    config = _load_config()

    # Extract and validate aliases
    aliases = config.get("aliases", {})
    if not isinstance(aliases, dict):
        raise ValueError("'aliases' must be a dictionary")

    # Extract and validate stopwords
    stopwords_list = config.get("stopwords", [])
    if not isinstance(stopwords_list, list):
        raise ValueError("'stopwords' must be a list")

    # Extract and validate units
    units_exact_list = config.get("units_exact", [])
    if not isinstance(units_exact_list, list):
        raise ValueError("'units_exact' must be a list")

    units_regex_patterns = config.get("units_regex", [])
    if not isinstance(units_regex_patterns, list):
        raise ValueError("'units_regex' must be a list")

    # Compile regex patterns
    try:
        regex_list = [re.compile(pattern) for pattern in units_regex_patterns]
    except re.error as e:
        raise ValueError(f"Invalid regex pattern in config: {e}")

    return {
        "aliases": aliases,
        "stopwords": frozenset(stopwords_list),
        "units_exact": frozenset(units_exact_list),
        "units_regex": regex_list,
    }


# Load configuration at module import time
_config = _initialize_config()

ALIAS_MAP: dict[str, list[str]] = _config["aliases"]
STOPWORDS: frozenset[str] = _config["stopwords"]
UNITS_EXACT: frozenset[str] = _config["units_exact"]
UNITS_REGEX: list[re.Pattern[str]] = _config["units_regex"]


def is_unit(token: str) -> bool:
    """Check if token is a measurement unit."""
    if token in UNITS_EXACT:
        return True
    return any(p.match(token) for p in UNITS_REGEX)


def is_stopword(token: str) -> bool:
    """Check if token is a stopword."""
    return token in STOPWORDS
