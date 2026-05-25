"""Consultation pipeline models."""

from pydantic import BaseModel

from src.common.bundle_builder import KBContextBundle
from src.fsm.models import SagaData, SagaInput
from src.store.knowledge_store import ChunkSearchResult


class ConsultRequest(SagaInput):
    """Input to the consultation pipeline."""

    user_request: str
    from_date: str | None = None
    """Optional search start date (ISO format YYYY-MM-DD). If not provided, defaults to lookback_days from config."""
    to_date: str | None = None
    """Optional search end date (ISO format YYYY-MM-DD). If not provided, defaults to today."""
    include_meta_chunks: bool = False
    """If False (default), chunks with kind='meta' are excluded from BM25 results.
    If True, meta chunks are included but ranked lower via meta_score_factor."""


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
