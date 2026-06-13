"""Domain exceptions raised by application services.

These are caught by the FastAPI exception handler and mapped to
standardized HTTP error responses with stable machine-readable codes.
"""


class AppError(Exception):
    """Base application error with a stable machine-readable code."""

    code: str = "internal_error"
    http_status: int = 500

    def __init__(self, message: str, details: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details


class NotFoundError(AppError):
    """Resource not found."""

    code = "not_found"
    http_status = 404


class LLMTimeoutError(AppError):
    """LLM request timed out after exhausting the retry budget."""

    code = "llm_timeout"
    http_status = 504


class LLMUnavailableError(AppError):
    """LLM service returned a 5xx error."""

    code = "llm_unavailable"
    http_status = 502


class LLMRequestInvalidError(AppError):
    """LLM service rejected the request (4xx)."""

    code = "llm_request_invalid"
    http_status = 400


class IngestFailedError(AppError):
    """Ingest saga pipeline failed."""

    code = "ingest_failed"
    http_status = 422


class InternalError(AppError):
    """Unexpected internal error."""

    code = "internal_error"
    http_status = 500


class UnauthorizedError(AppError):
    """Missing or invalid authentication."""

    code = "unauthorized"
    http_status = 401


class InvalidCredentialsError(AppError):
    """Wrong username or password."""

    code = "invalid_credentials"
    http_status = 401


class UsernameTakenError(AppError):
    """Registration username already exists."""

    code = "username_taken"
    http_status = 409


class UsernameReservedError(AppError):
    """Registration username is reserved."""

    code = "username_reserved"
    http_status = 409


class ProfileIncompleteError(AppError):
    """Profile must be completed before this action."""

    code = "profile_incomplete"
    http_status = 403


class ForbiddenError(AppError):
    """Insufficient permissions."""

    code = "forbidden"
    http_status = 403


class ValidationError(AppError):
    """Input validation failed."""

    code = "validation_error"
    http_status = 422
