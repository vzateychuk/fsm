from typing import Protocol

from src.llm.models import Message
from src.store.models import MessageRecord, SessionRecord


class InternalStore(Protocol):
    """
    Application internal persistent store (sessions and messages).

    Provides session metadata persistence and message history management.
    """

    async def upsert_session(self, session: SessionRecord) -> None:
        """Create or update a session record.

        Args:
            session: Session record to persist or update.
        """
        ...

    async def get_session(self, session_id: str) -> SessionRecord | None:
        """Retrieve a session by ID.

        Args:
            session_id: Session identifier.

        Returns:
            SessionRecord if found, None otherwise.
        """
        ...

    async def list_sessions(self, include_archived: bool = False) -> list[SessionRecord]:
        """List all sessions, optionally filtering out archived ones.

        Args:
            include_archived: If False, exclude sessions with status='archived'.

        Returns:
            List of SessionRecord, sorted by updated_at descending.
        """
        ...

    async def delete_session(self, session_id: str) -> None:
        """Delete a session and all its messages.

        Args:
            session_id: Session identifier.
        """
        ...

    async def save_messages(self, session_id: str, messages: list[Message]) -> None:
        """Save or update messages for a session.

        Replaces all messages for the session with the provided list.
        tool_calls are serialized to JSON format.

        Args:
            session_id: Session identifier.
            messages: List of Message objects to persist.
        """
        ...

    async def load_messages(self, session_id: str) -> list[Message]:
        """Load all messages for a session, in sequence order.

        Deserializes tool_calls from JSON format.

        Args:
            session_id: Session identifier.

        Returns:
            List of Message objects, ordered by seq ascending.
        """
        ...

    async def list_session_messages(
        self,
        session_id: str,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[MessageRecord]:
        """Return visible messages (user + final assistant) with DB metadata.

        Filters out tool messages and intermediate assistant messages that have
        tool_calls. Returns only the messages suitable for display in the UI.

        Args:
            session_id: Session identifier.
            limit: Maximum number of messages to return.
            offset: Number of messages to skip (for pagination).

        Returns:
            List of MessageRecord objects ordered by seq ascending.
        """
        ...

    async def get_last_assistant_message(self, session_id: str) -> MessageRecord | None:
        """Return the last final assistant message in a session.

        Args:
            session_id: Session identifier.

        Returns:
            The most recent assistant message (no tool_calls), or None if not found.
        """
        ...
