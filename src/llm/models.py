"""LLM message and request/response models."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Message:
    """A single message in a chat interaction."""

    role: str
    content: str


@dataclass(frozen=True)
class ChatRequest:
    """Request to the LLM for a chat completion."""

    messages: list[Message]


@dataclass(frozen=True)
class ChatResponse:
    """Response from the LLM."""

    text: str
