"""FastAPI dependency injection helpers.

All functions here extract application services from app.state.ctx,
which is populated during lifespan startup by create_app_context().
"""
from __future__ import annotations

from fastapi import Request

from src.api.config import ApiConfig
from src.services.chat import ChatService
from src.services.ingest import IngestService
from src.services.profile import ProfileService
from src.services.sessions import SessionsService


def get_sessions_service(request: Request) -> SessionsService:
    return request.app.state.ctx.sessions_service  # type: ignore[no-any-return]


def get_profile_service(request: Request) -> ProfileService:
    return request.app.state.ctx.profile_service  # type: ignore[no-any-return]


def get_ingest_service(request: Request) -> IngestService:
    return request.app.state.ctx.ingest_service  # type: ignore[no-any-return]


def get_chat_service(request: Request) -> ChatService:
    return request.app.state.ctx.chat_service  # type: ignore[no-any-return]


def get_api_config(request: Request) -> ApiConfig:
    return request.app.state.ctx.api_config  # type: ignore[no-any-return]
