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
    """
    admin_section_headings: frozenset[str]

    @classmethod
    def load(cls, config_path: Path) -> IngestConfig:
        """Load ingest config from YAML file."""
        with open(config_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        headings = data.get("admin_section_headings", [])
        return cls(
            admin_section_headings=frozenset(headings)
        )
