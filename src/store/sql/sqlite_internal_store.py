"""SQLite implementation of InternalStore for persistent sessions and messages."""

import json
from dataclasses import dataclass
from datetime import datetime, UTC
from uuid import uuid4

import aiosqlite

from src.llm.models import Message, ToolCall
from src.store.models import SessionRecord


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
