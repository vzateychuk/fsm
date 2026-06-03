"""Chat message endpoints — send a turn and retrieve history."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from src.api.deps import get_chat_service
from src.api.schemas import ChatTurnResponse, MessageDTO, SendMessageRequest
from src.services.chat import ChatService
from src.services.errors import (
    LLMRequestInvalidError,
    LLMTimeoutError,
    LLMUnavailableError,
    NotFoundError,
)

router = APIRouter(prefix="/api/v1/sessions", tags=["chat"])


@router.post("/{session_id}/messages", response_model=ChatTurnResponse)
async def send_message(
    session_id: str,
    body: SendMessageRequest,
    service: ChatService = Depends(get_chat_service),
) -> ChatTurnResponse:
    try:
        msg = await service.send_message(session_id, body.content)
    except NotFoundError:
        raise HTTPException(status_code=404, detail=f"Session {session_id!r} not found")
    except LLMTimeoutError as exc:
        raise HTTPException(status_code=504, detail=exc.message)
    except LLMUnavailableError as exc:
        raise HTTPException(status_code=502, detail=exc.message)
    except LLMRequestInvalidError as exc:
        raise HTTPException(status_code=400, detail=exc.message)
    return ChatTurnResponse(
        message_id=msg.message_id,
        role=msg.role,
        content=msg.content,
        created_at=msg.created_at,
    )


@router.get("/{session_id}/messages", response_model=list[MessageDTO])
async def list_messages(
    session_id: str,
    limit: int = 100,
    offset: int = 0,
    service: ChatService = Depends(get_chat_service),
) -> list[MessageDTO]:
    try:
        messages = await service.get_messages(session_id, limit=limit, offset=offset)
    except NotFoundError:
        raise HTTPException(status_code=404, detail=f"Session {session_id!r} not found")
    return [
        MessageDTO(
            message_id=m.message_id,
            session_id=m.session_id,
            role=m.role,
            content=m.content,
            created_at=m.created_at,
        )
        for m in messages
    ]
