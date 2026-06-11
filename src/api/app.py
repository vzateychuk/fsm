"""FastAPI application factory.

Creates the app with lifespan, CORS, and global exception handlers.
The app instance is module-level so uvicorn can reference 'src.api.app:app'.
"""
from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.api.factory import create_shared_context
from src.api.middleware import RequestIDFilter, RequestIDMiddleware
from src.api.routers import auth, chat, documents, health, profile, sessions
from src.services.errors import AppError

logger = logging.getLogger(__name__)


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.shared_ctx = await create_shared_context()
    logger.info("Application context initialized")
    yield
    logger.info("Application shutting down")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Med AI Adviser API",
        version="1.0.0",
        lifespan=_lifespan,
    )

    cors_origins_raw = os.getenv("CORS_ORIGINS", "http://localhost:5173")
    cors_origins = [o.strip() for o in cors_origins_raw.split(",") if o.strip()]
    # allow_credentials=True is incompatible with allow_origins=["*"] per CORS spec —
    # browsers reject preflight with credentials + wildcard origin.
    # Use allow_origins=["*"] only when credentials are not needed (e.g. public read-only).
    allow_credentials = cors_origins != ["*"]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestIDMiddleware)

    # Attach request-ID filter to root logger so every log record emitted
    # during a request automatically carries the correlation ID.
    logging.getLogger().addFilter(RequestIDFilter())

    # Domain errors from dependencies (UnauthorizedError, ProfileIncompleteError, …)
    # are converted here — no separate middleware required.
    @app.exception_handler(AppError)
    async def _app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.http_status,
            content={
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
            },
        )

    @app.exception_handler(Exception)
    async def _unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error("Unhandled exception: %s", exc, exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "code": "internal_error",
                "message": "An unexpected error occurred",
                "details": None,
            },
        )

    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(sessions.router)
    app.include_router(chat.router)
    app.include_router(documents.router)
    app.include_router(profile.router)

    return app


app = create_app()
