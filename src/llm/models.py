"""LLM message and request/response models."""

from dataclasses import dataclass, field


@dataclass
class ToolDefinition:
    """Definition of a tool that can be called by the LLM."""

    name: str
    description: str
    parameters: dict  # JSON Schema object


@dataclass
class ToolCall:
    """A tool call requested by the LLM in an assistant turn."""

    id: str
    name: str
    arguments: dict  # parsed from JSON


@dataclass
class Message:
    """A single message in a chat interaction."""

    role: str
    content: str
    tool_call_id: str | None = None
    """Set on role='tool' messages to link the result to a specific tool call."""
    tool_calls: list[ToolCall] | None = None
    """Set on role='assistant' messages when the model requests tool calls."""


@dataclass
class ToolResult:
    """Result content to return to the LLM for a specific tool call."""

    tool_call_id: str
    content: str


@dataclass
class ChatRequest:
    """Request to the LLM for a chat completion."""

    messages: list[Message]
    tools: list[ToolDefinition] = field(default_factory=list)
    """Tool definitions available to the model. Empty list disables tool use."""


@dataclass
class ChatResponse:
    """Response from the LLM."""

    text: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    """Tool calls requested by the model. Empty when the model returns text only."""
