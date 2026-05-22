"""Ingest pipeline configuration: admin section headings and other parameters."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class IngestConfig:
    """Configuration for ingest pipeline.

    Attributes:
        admin_section_headings: Set of normalized headings that mark administrative sections.
                               These chunks get kind="meta" during ChunkifyBlocks.
        max_section_chars: Maximum characters per section chunk before splitting at paragraph
                          boundaries. Does not apply to list/table/fact chunks.
    """
    admin_section_headings: frozenset[str]
    max_section_chars: int = 4000

    @classmethod
    def load(cls, config_path: Path) -> IngestConfig:
        """Load ingest config from YAML file."""
        with open(config_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        headings = data.get("admin_section_headings", [])
        return cls(
            admin_section_headings=frozenset(headings),
            max_section_chars=data.get("max_section_chars", 4000),
        )
