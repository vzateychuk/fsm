"""Chat consultation session models."""

from dataclasses import dataclass, field

from src.llm.models import Message


@dataclass
class ChatSession:
    """Represents the externally visible state of a chat consultation session.

    Holds the accumulated conversation history and a turn counter.
    Used by the CLI entrypoint to track session metadata; the conversation
    history is maintained internally by AgenticLoopRunner and exposed via
    its ``history`` property.
    """

    history: list[Message] = field(default_factory=list)
    turn_count: int = 0
