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
            ChatResponse with the fixed mock response.
        """
        self.last_request = req
        return ChatResponse(text=self.fixed_response)
