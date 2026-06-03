"""Session CRUD endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from src.api.deps import get_sessions_service
from src.api.schemas import CreateSessionRequest, PatchSessionRequest, SessionDTO
from src.services.sessions import SessionsService

router = APIRouter(prefix="/api/v1/sessions", tags=["sessions"])


def _to_dto(session: object) -> SessionDTO:
    return SessionDTO(
        session_id=session.session_id,  # type: ignore[attr-defined]
        title=session.title,  # type: ignore[attr-defined]
        status=session.status,  # type: ignore[attr-defined]
        created_at=session.created_at,  # type: ignore[attr-defined]
        updated_at=session.updated_at,  # type: ignore[attr-defined]
    )


@router.get("", response_model=list[SessionDTO])
async def list_sessions(
    status: str | None = None,
    service: SessionsService = Depends(get_sessions_service),
) -> list[SessionDTO]:
    sessions = await service.list_sessions(status=status)
    return [_to_dto(s) for s in sessions]


@router.post("", response_model=SessionDTO, status_code=201)
async def create_session(
    body: CreateSessionRequest,
    service: SessionsService = Depends(get_sessions_service),
) -> SessionDTO:
    session = await service.create_session(title=body.title)
    return _to_dto(session)


@router.get("/{session_id}", response_model=SessionDTO)
async def get_session(
    session_id: str,
    service: SessionsService = Depends(get_sessions_service),
) -> SessionDTO:
    session = await service.get_session(session_id)
    return _to_dto(session)


@router.patch("/{session_id}", response_model=SessionDTO)
async def update_session(
    session_id: str,
    body: PatchSessionRequest,
    service: SessionsService = Depends(get_sessions_service),
) -> SessionDTO:
    session = await service.update_session(
        session_id, title=body.title, status=body.status
    )
    return _to_dto(session)


@router.delete("/{session_id}", status_code=204)
async def delete_session(
    session_id: str,
    service: SessionsService = Depends(get_sessions_service),
) -> None:
    await service.delete_session(session_id)
