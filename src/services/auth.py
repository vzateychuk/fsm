"""AuthService — registration, login, sessions."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, UTC
from pathlib import Path
from uuid import uuid4

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from typing import TYPE_CHECKING

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
