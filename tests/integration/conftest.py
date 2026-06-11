"""Shared fixtures for HTTP integration tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.api.app import create_app

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def api_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.chdir(PROJECT_ROOT)
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("COOKIE_SECURE", "false")
    monkeypatch.setenv("SYSTEM_DB_PATH", str(tmp_path / "system.db"))
    monkeypatch.setenv("USER_DB_ROOT", str(tmp_path / "users"))
    with TestClient(create_app()) as client:
        yield client
