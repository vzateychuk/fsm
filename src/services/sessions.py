"""SessionsService — CRUD operations for chat sessions."""
from __future__ import annotations

import logging
from datetime import datetime, UTC
from uuid import uuid4

from src.store.internal_store import InternalStore
from src.store.models import SessionRecord
from src.services.errors import NotFoundError

logger = logging.getLogger(__name__)


def _normalize_status(status: str) -> str:
    """Normalize internal DB status to public API status.

    'pinned' is a CLI-only concept; API exposes it as 'active'.
    """
    return "active" if status == "pinned" else status


class SessionsService:
    """Application service for session lifecycle management."""

    def __init__(self, internal_store: InternalStore) -> None:
        self._store = internal_store

    async def list_sessions(self, status: str | None = None) -> list[SessionRecord]:
        """List sessions, optionally filtered by status.

        Args:
            status: 'active', 'archived', or None (all sessions).

        Returns:
            Sessions with normalized status.
        """
        include_archived = status != "active"
        sessions = await self._store.list_sessions(include_archived=include_archived)

        if status == "active":
            sessions = [s for s in sessions if s.status in ("active", "pinned")]
        elif status == "archived":
            sessions = [s for s in sessions if s.status == "archived"]

        for s in sessions:
            s.status = _normalize_status(s.status)

        logger.info("Listed %d sessions (filter=%s)", len(sessions), status)
        return sessions

    async def create_session(self, title: str = "New session") -> SessionRecord:
        """Create a new active session.

        Args:
            title: Session title (defaults to 'New session').

        Returns:
            The created SessionRecord.
        """
        session_id = str(uuid4())
        now = datetime.now(UTC).isoformat()
        session = SessionRecord(
            session_id=session_id,
            title=title,
            status="active",
            created_at=now,
            updated_at=now,
        )
        await self._store.upsert_session(session)
        logger.info("Created session: %s title=%r", session_id, title)
        return session

    async def get_session(self, session_id: str) -> SessionRecord:
        """Retrieve a session by ID.

        Args:
            session_id: Session identifier.

        Returns:
            The session with normalized status.

        Raises:
            NotFoundError: If the session does not exist.
        """
        session = await self._store.get_session(session_id)
        if session is None:
            raise NotFoundError(f"Session {session_id!r} not found")
        session.status = _normalize_status(session.status)
        return session

    async def update_session(
        self,
        session_id: str,
        title: str | None = None,
        status: str | None = None,
    ) -> SessionRecord:
        """Rename or change the status of a session.

        Args:
            session_id: Session identifier.
            title: New title (optional).
            status: New status — 'active' or 'archived' (optional).

        Returns:
            The updated session.

        Raises:
            NotFoundError: If the session does not exist.
        """
        session = await self._store.get_session(session_id)
        if session is None:
            raise NotFoundError(f"Session {session_id!r} not found")

        if title is not None:
            session.title = title
        if status is not None:
            session.status = status

        session.updated_at = datetime.now(UTC).isoformat()
        await self._store.upsert_session(session)
        session.status = _normalize_status(session.status)
        logger.info("Updated session: %s title=%r status=%r", session_id, title, status)
        return session

    async def delete_session(self, session_id: str) -> None:
        """Delete a session and all its messages.

        Args:
            session_id: Session identifier.

        Raises:
            NotFoundError: If the session does not exist.
        """
        session = await self._store.get_session(session_id)
        if session is None:
            raise NotFoundError(f"Session {session_id!r} not found")
        await self._store.delete_session(session_id)
        logger.info("Deleted session: %s", session_id)
