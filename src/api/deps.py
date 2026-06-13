"""FastAPI dependency injection helpers."""

from __future__ import annotations

from fastapi import Depends, Request

from src.api.config import ApiConfig
from src.api.user_context import SharedContext, UserContext
from src.api.user_resolver import auth_enabled, resolve_user_context
from src.services.chat import ChatService
from src.services.documents import DocumentsService
from src.services.errors import ForbiddenError, ProfileIncompleteError
from src.services.ingest import IngestService
from src.services.profile import ProfileService
from src.services.sessions import SessionsService


def get_shared_context(request: Request) -> SharedContext:
    return request.app.state.shared_ctx  # type: ignore[no-any-return]


async def get_user_context(
    user_ctx: UserContext = Depends(resolve_user_context),
) -> UserContext:
    return user_ctx


async def require_admin(
    user_ctx: UserContext = Depends(get_user_context),
) -> UserContext:
    """Require admin role."""
    if not auth_enabled():
        raise ForbiddenError("Admin API requires AUTH_ENABLED=true")
    if user_ctx.role != "admin":
        raise ForbiddenError("Admin access required")
    return user_ctx


async def require_complete_profile(
    user_ctx: UserContext = Depends(get_user_context),
) -> UserContext:
    """Require authenticated user with a complete profile.

    UnauthorizedError from get_user_context propagates to the global
    AppError exception handler (401 unauthorized) — not caught here.
    """
    profile = await user_ctx.profile_service.get_profile()
    if not ProfileService.is_complete(profile):
        raise ProfileIncompleteError("Complete your profile before using this feature.")
    return user_ctx


def get_sessions_service(
    user_ctx: UserContext = Depends(require_complete_profile),
) -> SessionsService:
    return user_ctx.sessions_service


def get_profile_service(
    user_ctx: UserContext = Depends(get_user_context),
) -> ProfileService:
    return user_ctx.profile_service


def get_documents_service(
    user_ctx: UserContext = Depends(require_complete_profile),
) -> DocumentsService:
    return user_ctx.documents_service


def get_ingest_service(
    user_ctx: UserContext = Depends(require_complete_profile),
) -> IngestService:
    return user_ctx.ingest_service


def get_chat_service(
    user_ctx: UserContext = Depends(require_complete_profile),
) -> ChatService:
    return user_ctx.chat_service


def get_api_config(request: Request) -> ApiConfig:
    return request.app.state.shared_ctx.api_config  # type: ignore[no-any-return]
