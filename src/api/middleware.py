"""Request-ID correlation middleware and logging support."""
from __future__ import annotations

import logging
from contextvars import ContextVar, Token
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

_request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


def get_request_id() -> str:
    """Return the current request ID, or '-' outside an HTTP request context."""
    return _request_id_var.get()


class RequestIDFilter(logging.Filter):
    """Inject the current request ID into every log record.

    Attach to the root logger so all loggers in the process automatically
    include the request ID in their output when a format string contains
    %(request_id)s.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = _request_id_var.get()
        return True


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Accept or generate a request ID and propagate it through async context.

    - Reads X-Request-ID from incoming headers; generates a UUID4 hex if absent.
    - Stores the ID in a ContextVar accessible from any coroutine in the request
      task tree so services and stores can log it without explicit threading.
    - Adds X-Request-ID to every response so clients can correlate log entries.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        request_id = request.headers.get("X-Request-ID") or uuid4().hex
        token: Token[str] = _request_id_var.set(request_id)
        try:
            response = await call_next(request)
        finally:
            _request_id_var.reset(token)
        response.headers["X-Request-ID"] = request_id
        return response
