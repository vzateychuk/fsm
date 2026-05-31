"""Chat consultation configuration.

AgenticLoopConfig  — agentic loop guardrails (roundtrips, budgets).
RecencyConfig      — recency bundle selection parameters.
ChatConfig         — main container; loads from config/chat.yaml.

BundleConfig and ExcerptsConfig are shared with src/pipelines/consult/ and
live in src/common/bundle_builder.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from src.common.bundle_builder import BundleConfig, ExcerptsConfig


@dataclass
class AgenticLoopConfig:
    """Guardrail parameters for the agentic KB query loop."""

    max_kb_roundtrips: int
    """Maximum number of KB tool roundtrips allowed per patient turn."""
    max_tool_calls_per_turn: int
    """Maximum number of tool_calls allowed in a single assistant turn."""
    max_search_chunks: int
    """Cap on chunks returned per tool call (applied silently before retrieval)."""
    max_search_chars: int
    """Cap on total characters in a kb.search_chunks tool result (applied at output)."""
    max_get_document_chars: int
    """Cap on total characters in a kb.get_document tool result (applied at output)."""


@dataclass
class RecencyConfig:
    """Configuration for the recency bundle (recent documents injected at turn start)."""

    max_docs: int
    """Maximum number of recent documents to include."""
    db_fetch_limit: int
    """Fetch limit for the database query (buffer above max_docs)."""
    chunks_per_doc: int
    """Number of leading chunks (ordered by chunk_no) taken from each recent document."""


@dataclass
class MemoryConfig:
    """Configuration for context compression and windowing."""

    window_turns: int
    """Number of most recent user turns to include in LLM context."""
    summarize_after_turns: int
    """Trigger rolling summary compression every N user turns."""


@dataclass
class ChatConfig:
    """Main chat consultation configuration container.

    Loads agentic loop guardrails, recency bundle settings, baseline
    context formatting parameters, and memory compression settings
    from config/chat.yaml.

    LLM configuration is loaded separately from config/llm.yaml via LLMConfig.
    Retrieval configuration is loaded separately from config/retrieve.yaml via RetrievalConfig.
    """

    agentic_loop: AgenticLoopConfig
    recency: RecencyConfig
    bundle: BundleConfig
    excerpts: ExcerptsConfig
    memory: MemoryConfig

    @classmethod
    def load(cls, config_path: Path) -> ChatConfig:
        """Load chat configuration from YAML file.

        Args:
            config_path: Path to config/chat.yaml.

        Returns:
            ChatConfig instance.
        """
        with open(config_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return cls(
            agentic_loop=AgenticLoopConfig(**data["agentic_loop"]),
            recency=RecencyConfig(**data["recency"]),
            bundle=BundleConfig(**data["bundle"]),
            excerpts=ExcerptsConfig(**data["excerpts"]),
            memory=MemoryConfig(**data["memory"]),
        )
