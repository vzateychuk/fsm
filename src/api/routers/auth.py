"""Authentication endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response

from src.api.cookies import SESSION_COOKIE_NAME, clear_session_cookie, set_session_cookie
from src.api.deps import get_shared_context, get_user_context
from src.api.schemas import AuthMeResponse, LoginRequest, RegisterRequest
from src.api.user_context import SharedContext, UserContext
from src.services.auth import AuthService
from src.services.profile import ProfileService

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def _auth(shared: SharedContext = Depends(get_shared_context)) -> AuthService:
    return shared.auth_service  # type: ignore[no-any-return]


@router.post("/register", status_code=201)
async def register(
    body: RegisterRequest,
    response: Response,
    auth: AuthService = Depends(_auth),
) -> AuthMeResponse:
    result = await auth.register(body.username, body.password)
    set_session_cookie(response, result.session_id)
    return AuthMeResponse(username=result.username, profile_complete=False, role="user")


@router.post("/login")
async def login(
    body: LoginRequest,
    response: Response,
    auth: AuthService = Depends(_auth),
    shared: SharedContext = Depends(get_shared_context),
) -> AuthMeResponse:
    result = await auth.login(body.username, body.password)
    set_session_cookie(response, result.session_id)
    account = await auth.resolve_account(result.username)
    assert account is not None

    # Admin has no user DB — skip profile check
    if account.role == "admin":
        return AuthMeResponse(
            username=result.username,
            profile_complete=True,
            role="admin",
        )

    user_ctx = await shared.user_factory.get(account.username, account.db_path)
    profile = await user_ctx.profile_service.get_profile()
    return AuthMeResponse(
        username=result.username,
        profile_complete=ProfileService.is_complete(profile),
        role="user",
    )


@router.post("/logout", status_code=204)
async def logout(
    request: Request,
    response: Response,
    auth: AuthService = Depends(_auth),
) -> None:
    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    if session_id:
        await auth.logout(session_id)
    clear_session_cookie(response)


@router.get("/me", response_model=AuthMeResponse)
async def me(
    user_ctx: UserContext = Depends(get_user_context),
) -> AuthMeResponse:
    # Admin has no user DB — skip profile check
    if user_ctx.role == "admin":
        return AuthMeResponse(
            username=user_ctx.username,
            profile_complete=True,
            role="admin",
        )
    profile = await user_ctx.profile_service.get_profile()
    return AuthMeResponse(
        username=user_ctx.username,
        profile_complete=ProfileService.is_complete(profile),
        role="user",
    )
