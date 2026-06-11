"""Auth and profile gate (Phase 7)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.api.app import create_app

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_register_login_profile_gate_and_chat(api_client: TestClient) -> None:
    reg = api_client.post(
        "/api/v1/auth/register",
        json={"username": "alice", "password": "password123"},
    )
    assert reg.status_code == 201
    assert reg.json()["profile_complete"] is False

    me = api_client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["username"] == "alice"

    blocked = api_client.get("/api/v1/sessions")
    assert blocked.status_code == 403
    assert blocked.json()["code"] == "profile_incomplete"

    patch = api_client.patch(
        "/api/v1/profile",
        json={
            "name": "Alice Test",
            "age": 35,
            "sex": "Female",
            "date_of_birth": "1990-05-01",
            "chronic_conditions": [],
            "current_medications": [],
            "allergies": [],
        },
    )
    assert patch.status_code == 200
    assert patch.json()["is_complete"] is True

    me2 = api_client.get("/api/v1/auth/me")
    assert me2.json()["profile_complete"] is True

    sessions = api_client.post("/api/v1/sessions", json={"title": "New session"})
    assert sessions.status_code == 201


def test_users_isolated_with_separate_cookies(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(PROJECT_ROOT)
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("COOKIE_SECURE", "false")
    user_root = tmp_path / "users"
    monkeypatch.setenv("USER_DB_ROOT", str(user_root))
    monkeypatch.setenv("SYSTEM_DB_PATH", str(tmp_path / "system.db"))

    with TestClient(create_app()) as client_a:
        r1 = client_a.post(
            "/api/v1/auth/register",
            json={"username": "usera", "password": "password123"},
        )
        assert r1.status_code == 201

    with TestClient(create_app()) as client_b:
        r2 = client_b.post(
            "/api/v1/auth/register",
            json={"username": "userb", "password": "password123"},
        )
        assert r2.status_code == 201

        patch = client_b.patch(
            "/api/v1/profile",
            json={
                "name": "B",
                "age": 40,
                "sex": "M",
                "date_of_birth": "1985-01-01",
                "chronic_conditions": [],
                "current_medications": [],
                "allergies": [],
            },
        )
        assert patch.status_code == 200

        docs = client_b.get("/api/v1/documents")
        assert docs.status_code == 200
        assert docs.json() == []
