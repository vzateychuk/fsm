"""Auth and profile gate HTTP status codes on protected endpoints."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def test_gated_endpoints_return_401_without_session(api_client: TestClient) -> None:
    """UnauthorizedError from resolve_user_context must not become 403 or 500."""
    cases: list[tuple[str, str, dict | None]] = [
        ("GET", "/api/v1/sessions", None),
        ("POST", "/api/v1/sessions", {"title": "x"}),
        ("GET", "/api/v1/documents", None),
        ("GET", "/api/v1/profile", None),
        (
            "PATCH",
            "/api/v1/profile",
            {
                "name": "X",
                "age": 1,
                "sex": "M",
                "date_of_birth": "2000-01-01",
                "chronic_conditions": [],
                "current_medications": [],
                "allergies": [],
            },
        ),
    ]
    for method, path, body in cases:
        if method == "GET":
            response = api_client.get(path)
        elif method == "POST":
            response = api_client.post(path, json=body)
        else:
            response = api_client.patch(path, json=body)

        assert response.status_code == 401, f"{method} {path} -> {response.status_code}"
        assert response.json()["code"] == "unauthorized"


def test_gated_endpoint_returns_403_not_401_when_profile_incomplete(api_client: TestClient) -> None:
    reg = api_client.post(
        "/api/v1/auth/register",
        json={"username": "gateuser", "password": "password123"},
    )
    assert reg.status_code == 201

    blocked = api_client.get("/api/v1/sessions")
    assert blocked.status_code == 403
    assert blocked.json()["code"] == "profile_incomplete"
