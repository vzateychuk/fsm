"""Mock LLM client for testing."""

from src.llm.models import ChatRequest, ChatResponse


class MockLLMClient:
    """Mock LLM client for testing purposes.

    Supports two modes:
    - Fixed response: always returns the same text (backwards-compatible default).
    - Response sequence: iterates through a list of ChatResponse objects, cycling
      on the last entry once the list is exhausted.

    Captures all requests for assertion in tests.
    """

    def __init__(
        self,
        fixed_response: str = "Mock medical answer.",
        responses: list[ChatResponse] | None = None,
    ) -> None:
        """Initialize the mock client.

        Args:
            fixed_response: Text returned for all requests when 'responses' is not set.
            responses: Ordered list of ChatResponse objects to return sequentially.
                Once exhausted, the last entry is repeated.
                Takes precedence over fixed_response when provided.
        """
        self.fixed_response = fixed_response
        self._responses = responses
        self.last_request: ChatRequest | None = None
        self.requests: list[ChatRequest] = []
        self._call_count = 0

    async def chat(self, req: ChatRequest) -> ChatResponse:
        """Execute a chat completion (mock).

        Args:
            req: Request containing messages.

        Returns:
            Next ChatResponse from the sequence, or a fixed-text ChatResponse.
        """
        self.last_request = req
        self.requests.append(req)

        if self._responses is not None:
            idx = min(self._call_count, len(self._responses) - 1)
            response = self._responses[idx]
        else:
            response = ChatResponse(text=self.fixed_response)

        self._call_count += 1
        return response
