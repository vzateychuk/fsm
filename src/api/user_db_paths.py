"""Resolve username and user database path from environment (CLI / Phase 6 HTTP)."""

from __future__ import annotations

import os
from pathlib import Path


def resolve_env_username() -> str:
    return os.getenv("USERNAME", "default")


def _validate_username_for_path(username: str) -> None:
    if not username or username in (".", ".."):
        raise ValueError(f"Invalid username for db path: {username!r}.")
    if any(sep in username for sep in ("/", "\\")):
        raise ValueError(f"Invalid username for db path: {username!r}.")


def _resolve_user_db_root() -> Path:
    raw = os.getenv("USER_DB_ROOT", ".data/db").strip()
    if not raw:
        raise ValueError("USER_DB_ROOT must not be empty.")
    root = Path(raw).expanduser()
    if not root.is_absolute():
        root = (Path.cwd() / root).resolve()
    else:
        root = root.resolve()
    return root


def resolve_user_db_path(username: str) -> str:
    _validate_username_for_path(username)
    root = _resolve_user_db_root()
    db_path = (root / f"{username}.db").resolve()
    try:
        db_path.relative_to(root)
    except ValueError as exc:
        raise ValueError(
            f"User db path {db_path} is outside USER_DB_ROOT {root}."
        ) from exc
    return str(db_path)


def resolve_env_db_path(username: str | None = None) -> str:
    explicit = os.getenv("DB_PATH")
    if explicit:
        return explicit
    user = username if username is not None else resolve_env_username()
    return resolve_user_db_path(user)


def ensure_db_parent(db_path: str) -> None:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)


def default_system_db_path() -> str:
    return os.getenv("SYSTEM_DB_PATH", ".data/db/system.db")
