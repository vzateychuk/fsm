"""Consultation pipeline configuration.
Each config subclass handles a specific aspect of the consultation pipeline:
- RecencyConfig: Controls selection and filtering of recent documents
- BundleConfig: Controls aggregation and limits for the knowledge base context bundle
- ExcerptsConfig: Controls formatting and truncation of text excerpts for the LLM
- ConsultConfig: Main container for all consultation-specific settings
- LLMConfig: Configuration for LLM client (extracted from consult.yaml)
"""
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
import yaml


@dataclass
class PatientInfo:
    """Patient demographic and clinical information.
    Loaded from config/patient.yaml.
    Used to populate Patient Info section in the consultation prompt.
    """
    name: str
    """Full patient name."""
    age: int
    """Patient age in years."""
    sex: str
    """Patient sex/gender."""
    date_of_birth: str
    """Patient date of birth (ISO format YYYY-MM-DD)."""
    chronic_conditions: list[str] = field(default_factory=list)
    """Known chronic conditions or diagnoses."""
    current_medications: list[str] = field(default_factory=list)
    """Current medications and dosages."""
    allergies: list[str] = field(default_factory=list)
    """Known allergies and adverse reactions."""

    @classmethod
    def load(cls, config_path: Path) -> "PatientInfo":
        """Load patient information from YAML file.
        Args:
            config_path: Path to config/patient.yaml
        Returns:
            PatientInfo instance with patient demographic and clinical data.
        """
        with open(config_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        patient_data = data.get("patient", {})
        return cls(**patient_data)


@dataclass
class RetrievalUsageConfig:
    """Configuration for consultation-context usage of the retrieval system (C1 step — Retrieve).
    These parameters control HOW the retrieval system is used within a consultation, not how the retrieval system itself works.
    The actual retrieval system configuration (BM25 weights, prefix matching, etc.) is stored in RetrievalConfig from config/retrieve.yaml.
    """
    query_top_k: int
    """Maximum number of chunks to fetch from BM25 query for the consultation. Passed as 'limit' to RetrieveRequest."""
    query_limit_per_document: int
    """Maximum chunks per document in the BM25 query results (diversity cap). Passed as 'limit_per_document' to RetrieveRequest."""


@dataclass
class RecencyConfig:
    """Configuration for the recency bundle (C1 step — Retrieve).
    The recency bundle supplements BM25 results with recent documents, ensuring the LLM has access to the most up-to-date information.
    These parameters control which documents are included and how many chunks per document.
    """
    max_docs: int
    """Maximum number of recent documents to include in the recency bundle."""
    max_age_days: int
    """Maximum age of documents in days. Documents older than this cutoff are excluded."""
    db_fetch_limit: int
    """Fetch limit for database query before date filtering on client side. Should be >= max_docs with some buffer to account for excluded old documents."""
    chunks_per_doc: int
    """Number of first chunks (ordered by chunk_no) to extract from each recent document."""


@dataclass
class BundleConfig:
    """Configuration for bundle assembly (C2 step — BuildBundle).
    The bundle aggregates query chunks (from BM25) and recency chunks into a single context block with enforced limits on quantity and size.
    These parameters ensure the final prompt fits within context limits and model constraints.
    """
    max_total_chunks: int
    """Hard limit on total chunks in the final bundle (query + recency combined).
    After this limit is applied, chunks are truncated by line count and then by character count.
    """
    max_total_chars: int
    """Hard limit on total characters in the final bundle.
    Applied AFTER line-truncation to protect against context overflow.
    Chunks are dropped from the tail until total size fits within this limit.
    """

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
    num_ctx: int = 16384
    """Context window size for model."""

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
            num_ctx=data.get("num_ctx", 16384),
        )


@dataclass
class ExcerptsConfig:
    """Configuration for excerpt formatting (C2 step — BuildBundle).
    Text excerpts are truncated based on their category to save context while preserving the most informative content.
    These parameters control which categories get full text vs. truncated text, and how aggressively to truncate.
    """
    top_chunks_count: int
    """Number of highest-ranked chunks to promote to 'Top Chunks' section in the prompt.
    These appear first and are visible to the LLM as primary results.
    """
    top_chunks_lines: int
    """Line limit for each chunk in the Top Chunks section.
    Each top chunk is truncated to this many lines.
    """
    max_lines_default: int
    """Default line limit for categories without explicit limits.
    Applied when truncating kb_excerpts section chunks.
    """
    full_text_categories: list[str] = field(default_factory=list)
    """Categories that should never be line-truncated (always show full text).
    Examples: 'Консультация', 'Выписка' — critical content that should not be cut.
    """
    category_line_limits: dict[str, int] = field(default_factory=dict)
    """Per-category line limits for truncation.
    Examples: {'Диагноз': 60, 'Анализы': 60}.
    Categories not in this dict fall back to max_lines_default.
    """


@dataclass
class ConsultConfig:
    """Main consultation pipeline configuration container.
    Loads all consultation-specific settings from config/consult.yaml.
    Retrieval system configuration is loaded separately from config/retrieve.yaml via RetrievalConfig.
    Used by ConsultRunner to configure all 5 pipeline steps (C0–C4).
    """
    retrieval: RetrievalUsageConfig
    """Configuration for consultation-context retrieval usage (C1 step).
    Controls limits and diversity for BM25 query results.
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
            ConsultConfig instance with all settings including retrieval, recency, bundle, and excerpts.

        Note:
            Retrieval system parameters are loaded separately from config/retrieve.yaml via RetrievalConfig.
            LLM configuration is loaded separately from config/llm.yaml via LLMConfig.load(Path('config/llm.yaml')).
        """
        with open(config_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return cls(
            retrieval=RetrievalUsageConfig(**data["retrieval"]),
            recency=RecencyConfig(**data["recency"]),
            bundle=BundleConfig(**data["bundle"]),
            excerpts=ExcerptsConfig(**data["excerpts"]),
        )
