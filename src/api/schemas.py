"""Pydantic DTOs for the REST API.

All request/response models live here. Services work with domain dataclasses;
these DTOs are the serialization boundary at the HTTP layer only.
"""
from __future__ import annotations

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Session DTOs
# ---------------------------------------------------------------------------


class SessionDTO(BaseModel):
    session_id: str
    title: str
    status: str
    created_at: str
    updated_at: str


class CreateSessionRequest(BaseModel):
    title: str = "New session"


class PatchSessionRequest(BaseModel):
    title: str | None = None
    status: str | None = None


# ---------------------------------------------------------------------------
# Chat DTOs
# ---------------------------------------------------------------------------


class SendMessageRequest(BaseModel):
    content: str


class ChatTurnResponse(BaseModel):
    message_id: str
    role: str
    content: str
    created_at: str


class MessageDTO(BaseModel):
    message_id: str
    session_id: str
    role: str
    content: str
    created_at: str


# ---------------------------------------------------------------------------
# Document DTOs
# ---------------------------------------------------------------------------


class DocumentDTO(BaseModel):
    id: str
    category: str
    document_date: str
    indexed_at: str


# ---------------------------------------------------------------------------
# Profile DTO
# ---------------------------------------------------------------------------


class ProfileDTO(BaseModel):
    name: str
    age: int
    sex: str
    date_of_birth: str
    chronic_conditions: list[str]
    current_medications: list[str]
    allergies: list[str]


# ---------------------------------------------------------------------------
# Error DTO
# ---------------------------------------------------------------------------


class ErrorResponse(BaseModel):
    code: str
    message: str
    details: str | None = None
