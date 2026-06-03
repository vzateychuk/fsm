"""API layer configuration."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class ApiConfig:
    """Configuration for the HTTP layer (timeouts, upload limits, pagination)."""

    consult_request_timeout_seconds: int = 300
    """Maximum wait time (seconds) for a synchronous chat turn."""
    upload_max_size_mb: int = 10
    """Maximum uploaded file size in megabytes."""
    pagination_default_limit: int = 100
    """Default page size for list endpoints."""
    pagination_max_limit: int = 500
    """Hard cap on page size for list endpoints."""

    @classmethod
    def load(cls, path: Path) -> ApiConfig:
        """Load API configuration from YAML file."""
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return cls(
            consult_request_timeout_seconds=data.get("consult_request_timeout_seconds", 300),
            upload_max_size_mb=data.get("upload_max_size_mb", 10),
            pagination_default_limit=data.get("pagination_default_limit", 100),
            pagination_max_limit=data.get("pagination_max_limit", 500),
        )
