"""OpenAI-compatible LLM client implementation."""

import json
import typing as t

from openai import AsyncOpenAI, APIError

from src.llm.errors import LLMError
from src.llm.models import ChatRequest, ChatResponse, Message, ToolCall
from src.llm.config import LLMConfig


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
            req: Request containing messages and optional tool definitions.

        Returns:
            ChatResponse with the LLM's text response and any requested tool calls.

        Raises:
            LLMError: If the API call fails.
        """
        try:
            messages = [self._serialize_message(msg) for msg in req.messages]

            request_kwargs: dict[str, t.Any] = {
                "model": self.cfg.model,
                "messages": messages,
                "temperature": self.cfg.temperature,
                "top_p": self.cfg.top_p,
                "stream": self.cfg.stream,
                "max_tokens": self.cfg.max_tokens,
            }

            if req.tools:
                request_kwargs["tools"] = [
                    {
                        "type": "function",
                        "function": {
                            "name": tool.name,
                            "description": tool.description,
                            "parameters": tool.parameters,
                        },
                    }
                    for tool in req.tools
                ]

            # Provider-specific thinking/CoT support (e.g. NVIDIA chat_template_kwargs).
            # enable_thinking=True translates to {"chat_template_kwargs": {"enable_thinking": True}}
            # unless already overridden via additional_request_kwargs.
            if self.cfg.enable_thinking and "chat_template_kwargs" not in self.cfg.additional_request_kwargs:
                request_kwargs["chat_template_kwargs"] = {"enable_thinking": True}

            # Merge any extra provider-specific keys (e.g. chat_template_kwargs overrides, seed, etc.)
            if self.cfg.additional_request_kwargs:
                request_kwargs.update(self.cfg.additional_request_kwargs)

            response = await self.client.chat.completions.create(**request_kwargs)

            message = response.choices[0].message
            text = message.content or ""

            tool_calls: list[ToolCall] = []
            if message.tool_calls:
                for tc in message.tool_calls:
                    tool_calls.append(
                        ToolCall(
                            id=tc.id,
                            name=tc.function.name,
                            arguments=json.loads(tc.function.arguments),
                        )
                    )

            return ChatResponse(text=text, tool_calls=tool_calls)
        except APIError as e:
            raise LLMError(f"LLM API error: {e}") from e

    @staticmethod
    def _serialize_message(msg: Message) -> dict[str, t.Any]:
        """Serialize a Message to the OpenAI API dict format."""
        d: dict[str, t.Any] = {"role": msg.role, "content": msg.content}
        if msg.tool_call_id is not None:
            d["tool_call_id"] = msg.tool_call_id
        if msg.tool_calls:
            d["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": json.dumps(tc.arguments, ensure_ascii=False),
                    },
                }
                for tc in msg.tool_calls
            ]
        return d
