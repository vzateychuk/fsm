"""SQLite implementation of InternalStore for persistent sessions and messages."""

import json
from dataclasses import dataclass
from datetime import datetime, UTC
from uuid import uuid4

import aiosqlite

from src.common.patient import PatientInfo
from src.llm.models import Message, ToolCall
from src.store.models import MessageRecord, SessionRecord


@dataclass(slots=True)
class SqliteInternalStore:
    """SQLite-backed implementation of session and message persistence."""

    db_path: str
    """Path to the SQLite database file."""

    async def upsert_session(self, session: SessionRecord) -> None:
        """Create or update a session record."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO sessions (session_id, title, status, summary, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    title = excluded.title,
                    status = excluded.status,
                    summary = excluded.summary,
                    updated_at = excluded.updated_at
                """,
                (
                    session.session_id,
                    session.title,
                    session.status,
                    session.summary,
                    session.created_at,
                    session.updated_at,
                ),
            )
            await db.commit()

    async def get_session(self, session_id: str) -> SessionRecord | None:
        """Retrieve a session by ID."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                SELECT session_id, title, status, summary, created_at, updated_at
                FROM sessions WHERE session_id = ?
                """,
                (session_id,),
            )
            row = await cursor.fetchone()
            if not row:
                return None
            return SessionRecord(
                session_id=row[0],
                title=row[1],
                status=row[2],
                summary=row[3],
                created_at=row[4],
                updated_at=row[5],
            )

    async def list_sessions(self, include_archived: bool = False) -> list[SessionRecord]:
        """List all sessions, optionally filtering out archived ones."""
        async with aiosqlite.connect(self.db_path) as db:
            if include_archived:
                query = """
                    SELECT session_id, title, status, summary, created_at, updated_at
                    FROM sessions ORDER BY updated_at DESC
                """
                cursor = await db.execute(query)
            else:
                query = """
                    SELECT session_id, title, status, summary, created_at, updated_at
                    FROM sessions WHERE status != 'archived' ORDER BY updated_at DESC
                """
                cursor = await db.execute(query)

            rows = await cursor.fetchall()
            return [
                SessionRecord(
                    session_id=row[0],
                    title=row[1],
                    status=row[2],
                    summary=row[3],
                    created_at=row[4],
                    updated_at=row[5],
                )
                for row in rows
            ]

    async def delete_session(self, session_id: str) -> None:
        """Delete a session and all its messages."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
            await db.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
            await db.commit()

    async def save_messages(self, session_id: str, messages: list[Message]) -> None:
        """Save or update messages for a session.

        Replaces all messages for the session with the provided list.
        """
        async with aiosqlite.connect(self.db_path) as db:
            # Clear existing messages for this session
            await db.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))

            # Insert new messages
            for seq, msg in enumerate(messages, start=1):
                message_id = str(uuid4())
                tool_calls_json = (
                    json.dumps([{"id": tc.id, "name": tc.name, "arguments": tc.arguments}
                                for tc in msg.tool_calls])
                    if msg.tool_calls
                    else None
                )

                await db.execute(
                    """
                    INSERT INTO messages
                    (message_id, session_id, seq, role, content, tool_call_id, tool_calls_json, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        message_id,
                        session_id,
                        seq,
                        msg.role,
                        msg.content,
                        msg.tool_call_id,
                        tool_calls_json,
                        datetime.now(UTC).isoformat(),
                    ),
                )

            await db.commit()

    async def load_messages(self, session_id: str) -> list[Message]:
        """Load all messages for a session, in sequence order."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                SELECT role, content, tool_call_id, tool_calls_json
                FROM messages WHERE session_id = ? ORDER BY seq ASC
                """,
                (session_id,),
            )
            rows = await cursor.fetchall()

            messages = []
            for role, content, tool_call_id, tool_calls_json in rows:
                tool_calls = None
                if tool_calls_json:
                    try:
                        tc_list = json.loads(tool_calls_json)
                        tool_calls = [
                            ToolCall(id=tc["id"], name=tc["name"], arguments=tc["arguments"])
                            for tc in tc_list
                        ]
                    except (json.JSONDecodeError, KeyError):
                        pass

                msg = Message(
                    role=role,
                    content=content,
                    tool_call_id=tool_call_id,
                    tool_calls=tool_calls,
                )
                messages.append(msg)

            return messages

    async def list_session_messages(
        self,
        session_id: str,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[MessageRecord]:
        """Return visible messages (user + final assistant) with DB metadata."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                SELECT message_id, session_id, role, content, created_at
                FROM messages
                WHERE session_id = ?
                  AND role IN ('user', 'assistant')
                  AND tool_calls_json IS NULL
                ORDER BY seq ASC
                LIMIT ? OFFSET ?
                """,
                (session_id, limit, offset),
            )
            rows = await cursor.fetchall()
            return [
                MessageRecord(
                    message_id=row[0],
                    session_id=row[1],
                    role=row[2],
                    content=row[3],
                    created_at=row[4],
                )
                for row in rows
            ]

    async def get_last_assistant_message(self, session_id: str) -> MessageRecord | None:
        """Return the last final assistant message in a session."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                SELECT message_id, session_id, role, content, created_at
                FROM messages
                WHERE session_id = ?
                  AND role = 'assistant'
                  AND tool_calls_json IS NULL
                ORDER BY seq DESC
                LIMIT 1
                """,
                (session_id,),
            )
            row = await cursor.fetchone()
            if row is None:
                return None
            return MessageRecord(
                message_id=row[0],
                session_id=row[1],
                role=row[2],
                content=row[3],
                created_at=row[4],
            )

    async def get_user_profile(self) -> PatientInfo | None:
        """Load singleton user profile row (id=1), or None if missing."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                SELECT name, age, sex, date_of_birth,
                       chronic_conditions_json, current_medications_json, allergies_json
                FROM user_profile WHERE id = 1
                """
            )
            row = await cursor.fetchone()
            if row is None:
                return None
            return PatientInfo(
                name=row[0],
                age=row[1],
                sex=row[2],
                date_of_birth=row[3],
                chronic_conditions=json.loads(row[4]),
                current_medications=json.loads(row[5]),
                allergies=json.loads(row[6]),
            )

    async def upsert_user_profile(self, profile: PatientInfo) -> None:
        """Insert or replace singleton user profile row."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO user_profile (
                    id, name, age, sex, date_of_birth,
                    chronic_conditions_json, current_medications_json, allergies_json
                ) VALUES (1, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    age = excluded.age,
                    sex = excluded.sex,
                    date_of_birth = excluded.date_of_birth,
                    chronic_conditions_json = excluded.chronic_conditions_json,
                    current_medications_json = excluded.current_medications_json,
                    allergies_json = excluded.allergies_json
                """,
                (
                    profile.name,
                    profile.age,
                    profile.sex,
                    profile.date_of_birth,
                    json.dumps(profile.chronic_conditions),
                    json.dumps(profile.current_medications),
                    json.dumps(profile.allergies),
                ),
            )
            await db.commit()
