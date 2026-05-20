"""Consultation pipeline configuration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class RetrievalConfig:
    query_top_k: int
    query_limit_per_document: int


@dataclass
class RecencyConfig:
    max_docs: int
    max_age_days: int
    db_fetch_limit: int
    chunks_per_doc: int


@dataclass
class BundleConfig:
    max_total_chunks: int
    max_total_chars: int


@dataclass
class ExcerptsConfig:
    top_chunks_count: int
    top_chunks_lines: int
    max_lines_default: int
    full_text_categories: list[str]
    category_line_limits: dict[str, int]


@dataclass
class ConsultConfig:
    retrieval: RetrievalConfig
    recency: RecencyConfig
    bundle: BundleConfig
    excerpts: ExcerptsConfig

    @classmethod
    def load(cls, config_path: Path) -> ConsultConfig:
        """Load configuration from YAML file (bundle and retrieval parameters only).

        LLM parameters are passed via environment variables to keep secrets separate.
        """
        with open(config_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        return cls(
            retrieval=RetrievalConfig(**data["retrieval"]),
            recency=RecencyConfig(**data["recency"]),
            bundle=BundleConfig(**data["bundle"]),
            excerpts=ExcerptsConfig(**data["excerpts"]),
        )
