"""Vendor-agnostic LLM client protocol."""

from typing import Protocol

from src.llm.models import ChatRequest, ChatResponse


class LLMClient(Protocol):
    """Protocol for LLM clients.

    Any implementation (OpenAI-compatible, local, etc.) must follow this interface.
    """

    async def chat(self, req: ChatRequest) -> ChatResponse:
        """Execute a chat completion request.

        Args:
            req: Request containing messages to send to the LLM.

        Returns:
            ChatResponse with the LLM's text response.

        Raises:
            LLMError: If the request fails.
        """
        ...
