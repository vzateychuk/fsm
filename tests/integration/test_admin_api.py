"""Integration tests for admin API endpoints."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def admin_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.chdir(PROJECT_ROOT)
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("COOKIE_SECURE", "false")
    monkeypatch.setenv("SYSTEM_DB_PATH", str(tmp_path / "system.db"))
    monkeypatch.setenv("USER_DB_ROOT", str(tmp_path / "users"))
    monkeypatch.setenv("ADMIN_PASSWORD", "adminpass123")
    with TestClient(create_app()) as client:
        yield client


@pytest.fixture
def user_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.chdir(PROJECT_ROOT)
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("COOKIE_SECURE", "false")
    monkeypatch.setenv("SYSTEM_DB_PATH", str(tmp_path / "system.db"))
    monkeypatch.setenv("USER_DB_ROOT", str(tmp_path / "users"))
    monkeypatch.setenv("ADMIN_PASSWORD", "adminpass123")
    with TestClient(create_app()) as client:
        # Register a regular user
        client.post(
            "/api/v1/auth/register",
            json={"username": "alice", "password": "password123"},
        )
        yield client


from src.api.app import create_app  # noqa: E402


class TestAdminListUsers:
    def test_requires_auth(self, admin_client: TestClient) -> None:
        response = admin_client.get("/api/v1/admin/users")
        assert response.status_code == 401

    def test_requires_admin_role(self, user_client: TestClient) -> None:
        response = user_client.get("/api/v1/admin/users")
        assert response.status_code == 403
        assert response.json()["code"] == "forbidden"

    def test_admin_can_list_users(self, admin_client: TestClient) -> None:
        # Login as admin
        login_response = admin_client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "adminpass123"},
        )
        assert login_response.status_code == 200

        # List users
        response = admin_client.get("/api/v1/admin/users")
        assert response.status_code == 200
        users = response.json()
        assert len(users) == 1
        assert users[0]["username"] == "admin"
        assert users[0]["role"] == "admin"


class TestAdminResetPassword:
    def test_admin_can_reset_password(self, admin_client: TestClient) -> None:
        # Register a user
        admin_client.post(
            "/api/v1/auth/register",
            json={"username": "bob", "password": "password123"},
        )

        # Login as admin
        admin_client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "adminpass123"},
        )

        # Reset bob's password
        response = admin_client.post(
            "/api/v1/admin/users/bob/reset-password",
            json={"new_password": "newpassword123"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

        # Old password should not work
        login_response = admin_client.post(
            "/api/v1/auth/login",
            json={"username": "bob", "password": "password123"},
        )
        assert login_response.status_code == 401

        # New password should work
        login_response = admin_client.post(
            "/api/v1/auth/login",
            json={"username": "bob", "password": "newpassword123"},
        )
        assert login_response.status_code == 200

    def test_non_admin_cannot_reset_password(self, user_client: TestClient) -> None:
        response = user_client.post(
            "/api/v1/admin/users/alice/reset-password",
            json={"new_password": "newpassword123"},
        )
        assert response.status_code == 403


class TestAdminSetRole:
    def test_admin_can_set_role(self, admin_client: TestClient) -> None:
        # Register a user
        admin_client.post(
            "/api/v1/auth/register",
            json={"username": "charlie", "password": "password123"},
        )

        # Login as admin
        admin_client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "adminpass123"},
        )

        # Promote charlie to admin
        response = admin_client.post(
            "/api/v1/admin/users/charlie/role",
            json={"role": "admin"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

        # Verify role changed
        users_response = admin_client.get("/api/v1/admin/users")
        charlie = next(u for u in users_response.json() if u["username"] == "charlie")
        assert charlie["role"] == "admin"

    def test_cannot_demote_last_admin(self, admin_client: TestClient) -> None:
        # Login as admin
        admin_client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "adminpass123"},
        )

        # Try to demote self (last admin)
        response = admin_client.post(
            "/api/v1/admin/users/admin/role",
            json={"role": "user"},
        )
        assert response.status_code == 403
        assert "last admin" in response.json()["message"]
