"""Admin API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from src.api.deps import get_shared_context, require_admin
from src.api.schemas import AdminUserDTO, ResetPasswordRequest, SetRoleRequest
from src.api.user_context import SharedContext, UserContext
from src.services.auth import AuthService

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


def _auth(shared: SharedContext = Depends(get_shared_context)) -> AuthService:
    return shared.auth_service  # type: ignore[no-any-return]


@router.get("/users", response_model=list[AdminUserDTO])
async def list_users(
    auth: AuthService = Depends(_auth),
    admin: UserContext = Depends(require_admin),
) -> list[AdminUserDTO]:
    accounts = await auth.list_accounts()
    return [
        AdminUserDTO(
            username=a.username,
            role=a.role,
            created_at=a.created_at,
        )
        for a in accounts
    ]


@router.post("/users/{username}/reset-password")
async def reset_password(
    username: str,
    body: ResetPasswordRequest,
    auth: AuthService = Depends(_auth),
    admin: UserContext = Depends(require_admin),
) -> dict[str, str]:
    await auth.admin_reset_password(username, body.new_password)
    return {"status": "ok"}


@router.post("/users/{username}/role")
async def set_role(
    username: str,
    body: SetRoleRequest,
    auth: AuthService = Depends(_auth),
    admin: UserContext = Depends(require_admin),
) -> dict[str, str]:
    await auth.admin_set_role(username, body.role, actor_username=admin.username)
    return {"status": "ok"}
