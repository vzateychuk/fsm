"""LLM client configuration."""

from __future__ import annotations

import os
import re
import typing as t
from dataclasses import dataclass, field
from pathlib import Path

import yaml


_ENV_VAR_RE = re.compile(
    r"\$(?:\{(?P<braced>[A-Za-z_][A-Za-z0-9_]*)\}|(?P<plain>[A-Za-z_][A-Za-z0-9_]*))"
)


def _expand_env_vars(value: t.Any) -> t.Any:
    """Recursively expand environment variables in YAML-loaded values.

    Supports:
        $VAR_NAME
        ${VAR_NAME}
    """

    if isinstance(value, str):
        def replace(match: re.Match[str]) -> str:
            env_name = match.group("braced") or match.group("plain")
            if env_name not in os.environ:
                raise ValueError(f"Environment variable {env_name!r} is not set")
            return os.environ[env_name]

        return _ENV_VAR_RE.sub(replace, value)

    if isinstance(value, dict):
        return {key: _expand_env_vars(item) for key, item in value.items()}

    if isinstance(value, list):
        return [_expand_env_vars(item) for item in value]

    return value


@dataclass
class LLMConfig:
    """Configuration for LLM client.

    Specifies the endpoint, authentication, model, and timeout for the LLM service.
    Supports OpenAI-compatible API endpoints.
    Loaded from config/llm.yaml; shared across all components (consult, chat, etc.).
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

        data = _expand_env_vars(data)

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