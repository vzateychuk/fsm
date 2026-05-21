"""Consultation pipeline models."""

from dataclasses import dataclass, field

from src.fsm.models import SagaData, SagaInput
from src.store.knowledge_store import ChunkSearchResult


class ConsultRequest(SagaInput):
    """Input to the consultation pipeline."""

    user_request: str


@dataclass
class KBContextBundle:
    """Formatted knowledge base context for the medical LLM."""

    top_chunks: list[str] = field(default_factory=list)
    kb_excerpts: list[str] = field(default_factory=list)
    provenance: list[str] = field(default_factory=list)


@dataclass
class ConsultResponse:
    """Final response from the LLM."""

    raw_text: str


@dataclass
class ConsultData(SagaData):
    """Pipeline state for consultation processing."""

    user_request: str = ""
    query_chunks: list[ChunkSearchResult] = field(default_factory=list)
    recency_chunks: list[ChunkSearchResult] = field(default_factory=list)
    bundle: KBContextBundle | None = None
    response: ConsultResponse | None = None
