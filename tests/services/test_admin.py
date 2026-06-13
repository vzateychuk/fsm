"""Tests for admin functionality (bootstrap, role, password reset)."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path

import pytest

from src.api.schema_init import ensure_system_schema
from src.services.auth import MIN_PASSWORD_LEN, ensure_admin_user
from src.store.sql.sqlite_system_store import AccountRecord, SqliteSystemStore


@pytest.fixture
async def system_store(tmp_path: Path) -> SqliteSystemStore:
    db_path = str(tmp_path / "system.db")
    await ensure_system_schema(db_path)
    return SqliteSystemStore(db_path=db_path)


@pytest.mark.asyncio
async def test_ensure_admin_user_creates_admin(system_store: SqliteSystemStore) -> None:
    os.environ["ADMIN_PASSWORD"] = "testpass123"
    try:
        await ensure_admin_user(system_store)

        accounts = await system_store.list_accounts()
        assert len(accounts) == 1
        assert accounts[0].username == "admin"
        assert accounts[0].role == "admin"
        assert accounts[0].db_path == ""  # sentinel
    finally:
        del os.environ["ADMIN_PASSWORD"]


@pytest.mark.asyncio
async def test_ensure_admin_user_skips_when_accounts_exist(
    system_store: SqliteSystemStore,
) -> None:
    # Create a non-admin account first
    await system_store.insert_account(
        AccountRecord(
            username="alice",
            password_hash="hash",
            role="user",
            db_path="/path/to/alice.db",
            created_at=datetime.now(UTC).isoformat(),
        )
    )

    os.environ["ADMIN_PASSWORD"] = "testpass123"
    try:
        await ensure_admin_user(system_store)

        accounts = await system_store.list_accounts()
        assert len(accounts) == 1
        assert accounts[0].username == "alice"
    finally:
        del os.environ["ADMIN_PASSWORD"]


@pytest.mark.asyncio
async def test_ensure_admin_user_skips_when_no_env(system_store: SqliteSystemStore) -> None:
    if "ADMIN_PASSWORD" in os.environ:
        del os.environ["ADMIN_PASSWORD"]

    # Should skip, not raise
    await ensure_admin_user(system_store)

    accounts = await system_store.list_accounts()
    assert len(accounts) == 0


@pytest.mark.asyncio
async def test_ensure_admin_user_requires_min_length(
    system_store: SqliteSystemStore,
) -> None:
    os.environ["ADMIN_PASSWORD"] = "short"
    try:
        with pytest.raises(RuntimeError, match="at least 8 characters"):
            await ensure_admin_user(system_store)
    finally:
        del os.environ["ADMIN_PASSWORD"]


@pytest.mark.asyncio
async def test_update_role(system_store: SqliteSystemStore) -> None:
    await system_store.insert_account(
        AccountRecord(
            username="bob",
            password_hash="hash",
            role="user",
            db_path="/path/to/bob.db",
            created_at=datetime.now(UTC).isoformat(),
        )
    )

    await system_store.update_role("bob", "admin")

    account = await system_store.get_account("bob")
    assert account is not None
    assert account.role == "admin"


@pytest.mark.asyncio
async def test_count_admins(system_store: SqliteSystemStore) -> None:
    assert await system_store.count_admins() == 0

    await system_store.insert_account(
        AccountRecord(
            username="admin1",
            password_hash="hash",
            role="admin",
            db_path="",
            created_at=datetime.now(UTC).isoformat(),
        )
    )
    assert await system_store.count_admins() == 1

    await system_store.insert_account(
        AccountRecord(
            username="user1",
            password_hash="hash",
            role="user",
            db_path="/path/to/user1.db",
            created_at=datetime.now(UTC).isoformat(),
        )
    )
    assert await system_store.count_admins() == 1

    await system_store.insert_account(
        AccountRecord(
            username="admin2",
            password_hash="hash",
            role="admin",
            db_path="",
            created_at=datetime.now(UTC).isoformat(),
        )
    )
    assert await system_store.count_admins() == 2
