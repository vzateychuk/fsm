"""Resolve UserContext for HTTP requests."""

from __future__ import annotations

import os

from fastapi import Request

from src.api.cookies import SESSION_COOKIE_NAME
from src.api.user_context import SharedContext, UserContext
from src.api.user_db_paths import resolve_env_db_path, resolve_env_username
from src.services.errors import UnauthorizedError


def auth_enabled() -> bool:
    return os.getenv("AUTH_ENABLED", "true").lower() not in ("0", "false", "no")


async def resolve_user_context(request: Request) -> UserContext:
    """Return UserContext for the current request."""
    shared: SharedContext = request.app.state.shared_ctx

    if not auth_enabled():
        username = resolve_env_username()
        db_path = resolve_env_db_path(username)
        return await shared.user_factory.get(username, db_path)

    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    if not session_id:
        raise UnauthorizedError("Authentication required.")

    session = await shared.auth_service.verify_session(session_id)
    if session is None:
        raise UnauthorizedError("Invalid or expired session.")

    account = await shared.auth_service.resolve_account(session.username)
    if account is None:
        raise UnauthorizedError("Account not found.")

    return await shared.user_factory.get(account.username, account.db_path)
