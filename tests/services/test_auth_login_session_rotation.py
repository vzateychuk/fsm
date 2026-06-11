"""Login rotates session_id by revoking prior auth_sessions for the user."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from argon2 import PasswordHasher
from fastapi.testclient import TestClient

from src.api.app import create_app
from src.services.auth import AuthService
from src.store.sql.sqlite_system_store import AccountRecord

PROJECT_ROOT = Path(__file__).resolve().parents[2]
_ph = PasswordHasher()


@pytest.mark.asyncio
async def test_login_deletes_existing_sessions_before_create() -> None:
    system = AsyncMock()
    system.get_account.return_value = AccountRecord(
        username="alice",
        password_hash=_ph.hash("password123"),
        db_path=".data/db/alice.db",
        created_at="2026-01-01T00:00:00+00:00",
    )
    user_factory = AsyncMock()
    auth = AuthService(system, user_factory)

    await auth.login("alice", "password123")

    system.delete_sessions_for_username.assert_awaited_once_with("alice")
    system.create_session.assert_awaited_once()


def test_login_invalidates_previous_session_cookie(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(PROJECT_ROOT)
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("COOKIE_SECURE", "false")
    monkeypatch.setenv("USER_DB_ROOT", str(tmp_path / "users"))
    monkeypatch.setenv("SYSTEM_DB_PATH", str(tmp_path / "system.db"))

    old_cookies: dict[str, str] = {}
    with TestClient(create_app()) as client:
        reg = client.post(
            "/api/v1/auth/register",
            json={"username": "rotuser", "password": "password123"},
        )
        assert reg.status_code == 201
        assert client.get("/api/v1/auth/me").status_code == 200
        old_cookies = dict(client.cookies)

    with TestClient(create_app()) as client:
        login = client.post(
            "/api/v1/auth/login",
            json={"username": "rotuser", "password": "password123"},
        )
        assert login.status_code == 200

    with TestClient(create_app()) as client:
        client.cookies.update(old_cookies)
        me = client.get("/api/v1/auth/me")
        assert me.status_code == 401
        assert me.json()["code"] == "unauthorized"
