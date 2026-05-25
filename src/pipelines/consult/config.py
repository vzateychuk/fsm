"""Consultation pipeline configuration.
Each config subclass handles a specific aspect of the consultation pipeline:
- RecencyConfig: Controls selection and filtering of recent documents
- ConsultConfig: Main container for all consultation-specific settings

BundleConfig and ExcerptsConfig are shared with src/chat/ and live in src/common/bundle_builder.
PatientInfo is shared with src/chat/ and lives in src/common/patient.
LLMConfig is shared across all components and lives in src/llm/config.py.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from src.common.bundle_builder import BundleConfig, ExcerptsConfig
from src.llm.config import LLMConfig  # re-exported for backwards compatibility


@dataclass
class RecencyConfig:
    """Configuration for the recency bundle (C1 step — Retrieve).
    The recency bundle supplements BM25 results with recent documents, ensuring
    the LLM has access to the most up-to-date information.
    """

    max_docs: int
    """Maximum number of recent documents to include in the recency bundle."""
    db_fetch_limit: int
    """Fetch limit for database query. Should be >= max_docs with some buffer."""
    chunks_per_doc: int
    """Number of first chunks (ordered by chunk_no) to extract from each recent document."""


@dataclass
class ConsultConfig:
    """Main consultation pipeline configuration container.
    Loads all consultation-specific settings from config/consult.yaml.

    Retrieval system configuration (BM25, limits, lookback) is loaded separately
    from config/retrieve.yaml via RetrievalConfig.
    LLM configuration is loaded separately from config/llm.yaml via LLMConfig.
    """

    recency: RecencyConfig
    """Configuration for the recency bundle selection (C1 step)."""
    bundle: BundleConfig
    """Configuration for bundle aggregation and sizing (C2 step)."""
    excerpts: ExcerptsConfig
    """Configuration for excerpt formatting and truncation (C2 step)."""

    @classmethod
    def load(cls, config_path: Path) -> "ConsultConfig":
        """Load consultation configuration from YAML file.

        Args:
            config_path: Path to config/consult.yaml

        Returns:
            ConsultConfig instance with recency, bundle, and excerpts settings.
        """
        with open(config_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return cls(
            recency=RecencyConfig(**data["recency"]),
            bundle=BundleConfig(**data["bundle"]),
            excerpts=ExcerptsConfig(**data["excerpts"]),
        )
