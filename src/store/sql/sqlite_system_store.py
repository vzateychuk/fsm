"""SQLite store for accounts and auth sessions (system.db)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import aiosqlite


@dataclass(frozen=True, slots=True)
class AccountRecord:
    username: str
    password_hash: str
    role: str  # 'admin' | 'user'
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
                INSERT INTO accounts (username, password_hash, role, db_path, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (account.username, account.password_hash, account.role, account.db_path, account.created_at),
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
                SELECT username, password_hash, role, db_path, created_at
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
                role=row[2],
                db_path=row[3],
                created_at=row[4],
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

    async def list_accounts(self) -> list[AccountRecord]:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT username, password_hash, role, db_path, created_at FROM accounts ORDER BY created_at"
            )
            rows = await cursor.fetchall()
            return [
                AccountRecord(
                    username=row[0],
                    password_hash=row[1],
                    role=row[2],
                    db_path=row[3],
                    created_at=row[4],
                )
                for row in rows
            ]

    async def update_password(self, username: str, password_hash: str) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE accounts SET password_hash = ? WHERE username = ?",
                (password_hash, username),
            )
            await db.commit()

    async def update_role(self, username: str, role: str) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE accounts SET role = ? WHERE username = ?",
                (role, username),
            )
            await db.commit()

    async def count_admins(self) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM accounts WHERE role = 'admin'")
            row = await cursor.fetchone()
            return row[0] if row else 0
