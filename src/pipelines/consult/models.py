"""Consultation pipeline models."""

from pydantic import BaseModel

from src.fsm.models import SagaData, SagaInput
from src.store.knowledge_store import ChunkSearchResult


class ConsultRequest(SagaInput):
    """Input to the consultation pipeline."""

    user_request: str
    from_date: str | None = None
    """Optional search start date (ISO format YYYY-MM-DD). If not provided, defaults to lookback_days from config."""
    to_date: str | None = None
    """Optional search end date (ISO format YYYY-MM-DD). If not provided, defaults to today."""


class KBContextBundle(BaseModel):
    """Formatted knowledge base context for the medical LLM."""

    top_chunks: list[str] = []
    kb_excerpts: list[str] = []
    provenance: list[str] = []


class ConsultResponse(BaseModel):
    """Final response from the LLM."""

    raw_text: str


class ConsultData(SagaData):
    """Pipeline state for consultation processing."""

    model_config = {"arbitrary_types_allowed": True}

    user_request: str = ""
    query_chunks: list[ChunkSearchResult] = []
    recency_chunks: list[ChunkSearchResult] = []
    bundle: KBContextBundle | None = None
    raw_answer: str = ""
    response: ConsultResponse | None = None
