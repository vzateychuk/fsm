"""Data models for internal store (sessions and messages)."""

from dataclasses import dataclass


@dataclass
class MessageRecord:
    """A single visible message (user or final assistant) with DB metadata."""

    message_id: str
    """Unique message identifier."""
    session_id: str
    """Session this message belongs to."""
    role: str
    """Message role: 'user' or 'assistant'."""
    content: str
    """Message text content."""
    created_at: str
    """ISO 8601 timestamp when the message was persisted."""


@dataclass
class SessionRecord:
    """Persistent record of a chat consultation session."""

    session_id: str
    """Unique session identifier."""
    title: str
    """Session title, defaults to first user message or manual edit."""
    status: str
    """Session status: 'active', 'pinned', or 'archived'."""
    created_at: str
    """ISO 8601 timestamp of session creation."""
    updated_at: str
    """ISO 8601 timestamp of last session update."""
    summary: str | None = None
    """Rolling summary of session content (Phase 3). None until first compression."""
