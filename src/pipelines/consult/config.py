"""Consultation pipeline configuration.
Each config subclass handles a specific aspect of the consultation pipeline:
- RecencyConfig: Controls selection and filtering of recent documents
- ConsultConfig: Main container for all consultation-specific settings
- LLMConfig: Configuration for LLM client (extracted from llm.yaml)

BundleConfig and ExcerptsConfig are shared with src/chat/ and live in src/common/bundle_builder.
PatientInfo is shared with src/chat/ and lives in src/common/patient.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import typing as t
import yaml

from src.common.bundle_builder import BundleConfig, ExcerptsConfig


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
class LLMConfig:
    """Configuration for LLM client (C3 step — CallPatientQuery).
    Specifies the endpoint, authentication, model, and timeout for the LLM service.
    Supports OpenAI-compatible API endpoints.
    """

    base_url: str
    """Base URL for OpenAI-compatible LLM endpoint (e.g., http://localhost:11434/v1)."""
    api_key: str
    """API key for authentication. Use 'none' for local endpoints without auth."""
    model: str
    """Model identifier (e.g., 'mistral', 'gpt-4')."""
    timeout: float
    """Request timeout in seconds."""
    temperature: float = 0.1
    """Sampling temperature."""
    top_p: float = 0.9
    """Top-p (nucleus) sampling parameter."""
    max_tokens: int = 8192
    """Maximum number of tokens to generate."""
    max_retries: int = 1
    """Number of retries on transient API errors."""
    num_ctx: int = 16384
    """Context window size for model."""
    stream: bool = False
    """Whether to stream the response."""
    enable_thinking: bool = False
    """Enable chain-of-thought / thinking mode (e.g. NVIDIA chat_template_kwargs)."""
    additional_request_kwargs: dict[str, t.Any] = field(default_factory=dict)
    """Extra provider-specific request parameters merged into the API call."""

    @classmethod
    def load(cls, config_path: Path) -> "LLMConfig":
        """Load LLM configuration from YAML file.

        Args:
            config_path: Path to config/llm.yaml

        Returns:
            LLMConfig instance.
        """
        with open(config_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return cls(
            base_url=data["base_url"],
            api_key=data["api_key"],
            model=data["model"],
            timeout=data["timeout"],
            temperature=data.get("temperature", 0.1),
            top_p=data.get("top_p", 0.9),
            max_tokens=data.get("max_tokens", 8192),
            max_retries=data.get("max_retries", 1),
            num_ctx=data.get("num_ctx", 16384),
            stream=data.get("stream", False),
            enable_thinking=data.get("enable_thinking", False),
            additional_request_kwargs=data.get("additional_request_kwargs", {}),
        )


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
