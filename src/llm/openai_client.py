"""OpenAI-compatible LLM client implementation."""

import typing as t

from openai import AsyncOpenAI, APIError

from src.llm.errors import LLMError
from src.llm.models import ChatRequest, ChatResponse
from src.pipelines.consult.config import LLMConfig



class OpenAICompatibleClient:
    """LLM client for OpenAI-compatible API endpoints.
    Supports any API that implements the OpenAI chat.completions interface (e.g., local Ollama, vLLM, or cloud endpoints).
    """

    def __init__(self, config: LLMConfig) -> None:
        """Initialize the OpenAI-compatible client.

        Args:
            config: LLMConfig instance with LLM client settings.
        """
        self.cfg = config
        self.client = AsyncOpenAI(
            base_url=config.base_url,
            api_key=config.api_key,
            timeout=config.timeout,
            max_retries=config.max_retries,
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
                {
                    "role": msg.role,
                    "content": msg.content,
                }
                for msg in req.messages
            ]

            request_kwargs: dict[str, t.Any] = {
                "model": self.cfg.model,
                "messages": messages,
                "temperature": self.cfg.temperature,
                "top_p": self.cfg.top_p,
                "stream": self.cfg.stream,
                "max_tokens": self.cfg.max_tokens,
            }

            # Provider-specific thinking/CoT support (e.g. NVIDIA chat_template_kwargs).
            # enable_thinking=True translates to {"chat_template_kwargs": {"enable_thinking": True}}
            # unless already overridden via additional_request_kwargs.
            if self.cfg.enable_thinking and "chat_template_kwargs" not in self.cfg.additional_request_kwargs:
                request_kwargs["chat_template_kwargs"] = {"enable_thinking": True}

            # Merge any extra provider-specific keys (e.g. chat_template_kwargs overrides, seed, etc.)
            if self.cfg.additional_request_kwargs:
                request_kwargs.update(self.cfg.additional_request_kwargs)

            response = await self.client.chat.completions.create(**request_kwargs)

            text = response.choices[0].message.content or ""
            return ChatResponse(text=text)
        except APIError as e:
            raise LLMError(f"LLM API error: {e}") from e
