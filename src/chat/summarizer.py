"""Rolling summary compression for context window management.

Compresses older conversation turns into a concise clinical summary
to keep unbounded message history within LLM context limits.
"""

from pathlib import Path

from src.llm.llm_client import LLMClient
from src.llm.models import ChatRequest, Message


async def summarize(
        llm_client: LLMClient,
        previous_summary: str | None,
        messages_to_compress: list[Message],
        summarizer_prompt_path: str = "prompts/chat/summarize.md",
) -> str:
    """Generate a rolling summary of conversation turns for context compression.

    Extracts the summarizer prompt template, formats it with the previous
    summary and serialized message history, and calls the LLM to produce
    a concise clinical summary.

    Args:
        llm_client: LLM client for the summarization request.
        previous_summary: Prior rolling summary (or None if first compression).
        messages_to_compress: List of messages to compress (typically outside the window).
        summarizer_prompt_path: Path to summarizer prompt template.

    Returns:
        New rolling summary string (suitable for prepending to next context).
    """
    prompt_template = Path(summarizer_prompt_path).read_text(encoding="utf-8")
    serialized_messages = _serialize_messages(messages_to_compress)
    previous_summary_text = previous_summary or "(no prior summary)"

    user_content = prompt_template.format(
        previous_summary=previous_summary_text, conversation=serialized_messages
    )

    # Call LLM to generate summary (no tools, single user message)
    request = ChatRequest(
        messages=[Message(role="user", content=user_content)], tools=[]
    )
    response = await llm_client.chat(request)
    return response.text


def _serialize_messages(messages: list[Message]) -> str:
    """Serialize message history as plain text for summarization.

    Tool calls are shown as `[tool call: name(arg1=value1, ...)]`
    Tool results are shown as `[tool result]: content`

    Args:
        messages: List of messages to serialize.

    Returns:
        Plain text serialization of the messages.
    """
    lines = []
    for msg in messages:
        if msg.role == "tool":
            lines.append(f"[tool result]: {msg.content}")
        elif msg.tool_calls:
            # Assistant turn with tool calls
            tool_calls_str = ", ".join(tc.name for tc in msg.tool_calls)
            lines.append(f"[assistant]: {msg.content}")
            lines.append(f"[tool calls]: {tool_calls_str}")
        else:
            lines.append(f"[{msg.role}]: {msg.content}")
    return "\n".join(lines)
