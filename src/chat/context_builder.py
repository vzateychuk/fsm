"""Context window builder for bounded LLM context.

Applies windowing to conversation history to keep recent context
in focus while optionally prepending a rolling summary of prior turns.
"""

from src.llm.models import Message


def build_context_messages(
        system_message: str,
        history: list[Message],
        summary: str | None,
        window_turns: int,
) -> list[Message]:
    """Build LLM context with optional windowing and rolling summary.

    Returns a list of messages suitable for sending to the LLM:
    1. Main system message
    2. (Optional) Summary of prior conversation (if summary is not None)
    3. Windowed history (last N user turns + all subsequent turns)

    Args:
        system_message: The main system prompt (e.g., patient info, policies).
        history: Full conversation history (user, assistant, tool messages).
        summary: Rolling summary of prior turns (or None if no prior context).
        window_turns: Number of most recent user turns to include.

    Returns:
        List of messages to send to LLM (system + optional summary + windowed history).
    """
    messages: list[Message] = []

    # 1. Main system message
    messages.append(Message(role="system", content=system_message))

    # 2. Prepend rolling summary if available
    if summary:
        messages.append(
            Message(
                role="system",
                content=f"<chat_history_summary>\n{summary}\n</chat_history_summary>",
            )
        )

    # 3. Apply windowing to history
    window_start = _find_window_start(history, window_turns)
    messages.extend(history[window_start:])

    return messages


def _find_window_start(history: list[Message], window_turns: int) -> int:
    """Find the starting index of the windowed history.

    Logic: count user messages from the end backwards; find the index where
    we cross the window_turns threshold. All messages from that index onward
    are included.

    If history has fewer user messages than window_turns, return 0 (include all).

    Args:
        history: Full conversation history.
        window_turns: Number of user turns to include.

    Returns:
        Starting index of the window (0 if entire history fits).
    """
    if window_turns <= 0:
        return len(history)

    # Count user messages from the end
    user_count = 0
    for i in range(len(history) - 1, -1, -1):
        if history[i].role == "user":
            user_count += 1
            if user_count >= window_turns:
                # Found the cutoff user turn; return its index
                return i

    # Fewer user turns than window_turns — include all history
    return 0
