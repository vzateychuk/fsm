"""AuthService — registration, login, sessions."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from src.api.schema_init import ensure_schema
from src.api.user_db_paths import resolve_user_db_path

if TYPE_CHECKING:
    from src.api.user_context import UserContextFactory
from src.common.patient import PatientInfo
from src.common.username import RESERVED_USERNAMES, validate_username
from src.services.errors import (
    InvalidCredentialsError,
    UsernameReservedError,
    UsernameTakenError,
    ValidationError,
)
from src.store.sql.sqlite_system_store import AccountRecord, AuthSessionRecord, SqliteSystemStore

logger = logging.getLogger(__name__)

_ph = PasswordHasher()
MIN_PASSWORD_LEN = 8


async def ensure_admin_user(store: SqliteSystemStore) -> None:
    """Create admin account when system.db has zero accounts.

    If ADMIN_PASSWORD is not set, skip bootstrap (operator can create admin manually).
    """
    if await store.list_accounts():
        return
    admin_password = os.getenv("ADMIN_PASSWORD")
    if not admin_password:
        logger.info("ADMIN_PASSWORD not set — skipping admin bootstrap")
        return
    if len(admin_password) < MIN_PASSWORD_LEN:
        raise RuntimeError("ADMIN_PASSWORD must be at least 8 characters")
    await store.insert_account(
        AccountRecord(
            username="admin",
            password_hash=_ph.hash(admin_password),
            role="admin",
            db_path="",  # sentinel: no user DB
            created_at=datetime.now(UTC).isoformat(),
        )
    )
    logger.info("Bootstrap: created admin user")


@dataclass(frozen=True, slots=True)
class AuthResult:
    session_id: str
    username: str


class AuthService:
    def __init__(
        self,
        system_store: SqliteSystemStore,
        user_factory: UserContextFactory,  # noqa: F821
    ) -> None:
        self._system = system_store
        self._user_factory = user_factory

    async def register(self, username: str, password: str) -> AuthResult:
        err = validate_username(username)
        if err:
            if username in RESERVED_USERNAMES:
                raise UsernameReservedError(err)
            raise ValidationError(err)
        if len(password) < MIN_PASSWORD_LEN:
            raise ValidationError(f"Password must be at least {MIN_PASSWORD_LEN} characters.")

        if await self._system.username_exists(username):
            raise UsernameTakenError(f"Username {username!r} is already taken.")

        db_path = resolve_user_db_path(username)
        password_hash = _ph.hash(password)
        created_at = datetime.now(UTC).isoformat()

        await self._system.insert_account(
            AccountRecord(
                username=username,
                password_hash=password_hash,
                role="user",
                db_path=db_path,
                created_at=created_at,
            )
        )

        try:
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
            await ensure_schema(db_path)
            user_ctx = await self._user_factory.get(username, db_path)
            await user_ctx.profile_service.update_profile(
                PatientInfo(name="", age=0, sex="", date_of_birth="")
            )
        except Exception:
            await self._system.delete_account(username)
            try:
                if Path(db_path).exists():
                    Path(db_path).unlink()
            except OSError as cleanup_err:
                logger.warning(
                    "Failed to remove user db during registration rollback %s: %s",
                    db_path,
                    cleanup_err,
                )
            raise

        return await self._create_session(username)

    async def login(self, username: str, password: str) -> AuthResult:
        account = await self._system.get_account(username)
        if account is None:
            raise InvalidCredentialsError("Invalid username or password.")
        try:
            _ph.verify(account.password_hash, password)
        except VerifyMismatchError as exc:
            raise InvalidCredentialsError("Invalid username or password.") from exc
        await self._system.delete_sessions_for_username(username)
        return await self._create_session(username)

    async def logout(self, session_id: str) -> None:
        await self._system.delete_session(session_id)

    async def verify_session(self, session_id: str) -> AuthSessionRecord | None:
        return await self._system.get_session(session_id)

    async def resolve_account(self, username: str) -> AccountRecord | None:
        return await self._system.get_account(username)

    async def _create_session(self, username: str) -> AuthResult:
        session_id = str(uuid4())
        await self._system.create_session(session_id, username)
        return AuthResult(session_id=session_id, username=username)

    async def list_accounts(self) -> list[AccountRecord]:
        """List all accounts (admin only)."""
        return await self._system.list_accounts()

    async def admin_reset_password(self, username: str, new_password: str) -> None:
        """Reset user password (admin only). Invalidates all sessions."""
        if len(new_password) < MIN_PASSWORD_LEN:
            raise ValidationError(f"Password must be at least {MIN_PASSWORD_LEN} characters.")
        account = await self._system.get_account(username)
        if account is None:
            from src.services.errors import NotFoundError
            raise NotFoundError(f"User {username!r} not found.")
        password_hash = _ph.hash(new_password)
        await self._system.update_password(username, password_hash)
        await self._system.delete_sessions_for_username(username)
        logger.info("Admin reset password for user %s", username)

    async def admin_set_role(self, username: str, role: str, *, actor_username: str) -> None:
        """Set user role (admin only). Forbids demoting the last admin."""
        if role not in ("admin", "user"):
            raise ValidationError("Role must be 'admin' or 'user'")
        account = await self._system.get_account(username)
        if account is None:
            from src.services.errors import NotFoundError
            raise NotFoundError(f"User {username!r} not found.")
        # Forbid demoting the last admin
        if account.role == "admin" and role != "admin":
            admin_count = await self._system.count_admins()
            if admin_count <= 1:
                from src.services.errors import ForbiddenError
                raise ForbiddenError("Cannot demote the last admin.")
        await self._system.update_role(username, role)
        logger.info("Admin set role=%s for user %s", role, username)
