"""SQLite store for accounts and auth sessions (system.db)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, UTC

import aiosqlite


@dataclass(frozen=True, slots=True)
class AccountRecord:
    username: str
    password_hash: str
    db_path: str
    created_at: str


@dataclass(frozen=True, slots=True)
class AuthSessionRecord:
    session_id: str
    username: str
    created_at: str


@dataclass(slots=True)
class SqliteSystemStore:
    db_path: str

    async def insert_account(self, account: AccountRecord) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO accounts (username, password_hash, db_path, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (account.username, account.password_hash, account.db_path, account.created_at),
            )
            await db.commit()

    async def delete_account(self, username: str) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM accounts WHERE username = ?", (username,))
            await db.commit()

    async def get_account(self, username: str) -> AccountRecord | None:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                SELECT username, password_hash, db_path, created_at
                FROM accounts WHERE username = ?
                """,
                (username,),
            )
            row = await cursor.fetchone()
            if row is None:
                return None
            return AccountRecord(
                username=row[0],
                password_hash=row[1],
                db_path=row[2],
                created_at=row[3],
            )

    async def username_exists(self, username: str) -> bool:
        return await self.get_account(username) is not None

    async def create_session(self, session_id: str, username: str) -> AuthSessionRecord:
        created_at = datetime.now(UTC).isoformat()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO auth_sessions (session_id, username, created_at)
                VALUES (?, ?, ?)
                """,
                (session_id, username, created_at),
            )
            await db.commit()
        return AuthSessionRecord(session_id=session_id, username=username, created_at=created_at)

    async def get_session(self, session_id: str) -> AuthSessionRecord | None:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                SELECT session_id, username, created_at
                FROM auth_sessions WHERE session_id = ?
                """,
                (session_id,),
            )
            row = await cursor.fetchone()
            if row is None:
                return None
            return AuthSessionRecord(session_id=row[0], username=row[1], created_at=row[2])

    async def delete_session(self, session_id: str) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM auth_sessions WHERE session_id = ?", (session_id,))
            await db.commit()

    async def delete_sessions_for_username(self, username: str) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "DELETE FROM auth_sessions WHERE username = ?",
                (username,),
            )
            await db.commit()
            return cursor.rowcount
