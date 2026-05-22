"""Mock LLM client for testing."""

from src.llm.models import ChatRequest, ChatResponse


class MockLLMClient:
    """Mock LLM client for testing purposes.

    Always returns a fixed response, but captures the request for verification.
    """

    def __init__(self, fixed_response: str = "Mock medical answer.") -> None:
        """Initialize the mock client.

        Args:
            fixed_response: The fixed response text to return for all requests.
        """
        self.fixed_response = fixed_response
        self.last_request: ChatRequest | None = None

    async def chat(self, req: ChatRequest) -> ChatResponse:
        """Execute a chat completion (mock).

        Args:
            req: Request containing messages.

        Returns:
            ChatResponse with the fixed mock response plus echoed request.
        """
        self.last_request = req

        # Format response and request for display
        response_echo = self._format_response()
        request_echo = self._format_request(req)
        full_text = f"{response_echo}\n\n{request_echo}"

        return ChatResponse(text=full_text)

    def _format_response(self) -> str:
        """Format response for display."""
        lines = ["=== RESPONSE ===\n", self.fixed_response]
        return "\n".join(lines)

    @staticmethod
    def _format_request(req: ChatRequest) -> str:
        """Format request for display."""
        lines = ["=== REQUEST ==="]
        for msg in req.messages:
            lines.append(f"\n[{msg.role.upper()}]")
            lines.append(msg.content[:500])  # First chars
        return "\n".join(lines)
