"""Retry wrapper for LLM clients with exponential backoff for timeout errors."""

import asyncio
import logging

from src.llm.errors import LLMError
from src.llm.llm_client import LLMClient
from src.llm.models import ChatRequest, ChatResponse

logger = logging.getLogger(__name__)


class RetryConfig:
    """Configuration for retry logic with exponential backoff.

    Attributes:
        max_retries: Maximum number of retry attempts (not counting the initial request).
        initial_delay_sec: Initial delay before first retry, in seconds.
        max_delay_sec: Maximum delay between retries, in seconds.
        backoff_factor: Multiplier for delay on each retry (exponential backoff).
        timeout_keywords: Tuple of error message substrings that indicate a timeout.
    """

    def __init__(
            self,
            max_retries: int = 3,
            initial_delay_sec: float = 1.0,
            max_delay_sec: float = 30.0,
            backoff_factor: float = 2.0,
            timeout_keywords: tuple[str, ...] = ("timed out", "timeout", "ReadTimeout"),
    ) -> None:
        self.max_retries = max_retries
        self.initial_delay_sec = initial_delay_sec
        self.max_delay_sec = max_delay_sec
        self.backoff_factor = backoff_factor
        self.timeout_keywords = timeout_keywords

    def is_timeout_error(self, error_message: str) -> bool:
        """Check if the error message indicates a timeout.

        Args:
            error_message: The error message to check.

        Returns:
            True if the message contains any timeout keyword (case-insensitive).
        """
        lower_msg = error_message.lower()
        return any(keyword.lower() in lower_msg for keyword in self.timeout_keywords)

    def get_delay(self, attempt: int) -> float:
        """Calculate delay for the given retry attempt number.

        Args:
            attempt: Retry attempt number (0-indexed).

        Returns:
            Delay in seconds, capped at max_delay_sec.
        """
        delay = self.initial_delay_sec * (self.backoff_factor ** attempt)
        return min(delay, self.max_delay_sec)


class RetryLLMClient:
    """Wrapper for LLMClient with exponential backoff retry logic.

    Intercepts timeout errors and retries the request with increasing delays.
    Non-timeout errors are raised immediately.

    Usage:
        wrapped_client = RetryLLMClient(base_client, retry_config)
        response = await wrapped_client.chat(request)
    """

    def __init__(self, base_client: LLMClient, retry_config: RetryConfig | None = None) -> None:
        """Initialize the retry wrapper.

        Args:
            base_client: The underlying LLM client to wrap.
            retry_config: Retry configuration. Defaults to RetryConfig() if not provided.
        """
        self._client = base_client
        self._retry_config = retry_config or RetryConfig()

    async def chat(self, req: ChatRequest) -> ChatResponse:
        """Execute a chat request with exponential backoff retry for timeout errors.

        Args:
            req: ChatRequest to send to the LLM.

        Returns:
            ChatResponse from the LLM.

        Raises:
            LLMError: If the request fails after all retries are exhausted,
                     or if a non-timeout error occurs.
        """
        last_error: LLMError | None = None

        for attempt in range(self._retry_config.max_retries + 1):
            try:
                return await self._client.chat(req)
            except LLMError as e:
                error_msg = str(e)

                if not self._retry_config.is_timeout_error(error_msg):
                    # Non-timeout error — fail immediately
                    logger.error(
                        "LLM request failed (non-timeout error, no retry): %s",
                        error_msg,
                    )
                    raise

                last_error = e

                if attempt < self._retry_config.max_retries:
                    delay = self._retry_config.get_delay(attempt)
                    logger.warning(
                        "LLM timeout error (attempt %d/%d), retrying in %.1fs: %s",
                        attempt + 1,
                        self._retry_config.max_retries + 1,
                        delay,
                        error_msg,
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        "LLM timeout error exhausted after %d retries: %s",
                        self._retry_config.max_retries + 1,
                        error_msg,
                    )

        if last_error:
            raise last_error

        # Should never reach here, but raise a generic error if we do
        raise LLMError("Unexpected error: retry loop completed without result")
