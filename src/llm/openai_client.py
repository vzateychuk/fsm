"""OpenAI-compatible LLM client implementation."""

from openai import AsyncOpenAI, APIError

from src.llm.errors import LLMError
from src.llm.models import ChatRequest, ChatResponse


class OpenAICompatibleClient:
    """LLM client for OpenAI-compatible API endpoints.

    Supports any API that implements the OpenAI chat.completions interface
    (e.g., local Ollama, vLLM, or cloud endpoints).
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        timeout: float = 60.0,
    ) -> None:
        """Initialize the OpenAI-compatible client.

        Args:
            base_url: API endpoint URL (e.g., "http://localhost:11434/v1").
            api_key: API key for authentication (use "none" for local models).
            model: Model identifier (e.g., "mistral", "gpt-4", etc.).
            timeout: Request timeout in seconds.
        """
        self.model = model
        self.client = AsyncOpenAI(
            base_url=base_url,
            api_key=api_key,
            timeout=timeout,
        )

    async def chat(self, req: ChatRequest) -> ChatResponse:
        """Execute a chat completion request.

        Args:
            req: Request containing messages.

        Returns:
            ChatResponse with the LLM's text response.

        Raises:
            LLMError: If the API call fails.
        """
        try:
            messages = [
                {"role": msg.role, "content": msg.content}
                for msg in req.messages
            ]
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
            )
            text = response.choices[0].message.content or ""
            return ChatResponse(text=text)
        except APIError as e:
            raise LLMError(f"LLM API error: {e}") from e
