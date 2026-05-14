from fsm.models import SagaInput, SagaData
from pydantic import Field


class IngestInput(SagaInput):
    """Input data for ingest pipeline"""

    source_path: str


class IngestData(SagaData):
    """Data for ingest pipeline"""

    desc: str | None = None

    # S1: Load source
    raw_content: str | None = None
    file_hash: str | None = None

    # S3: Detect target schema
    target_schema: str | None = None

    # S4: Split control blocks
    schema_line: str | None = None
    metadata_block: str | None = None
    md_body: str | None = None

    # S5: Parse to tokens
    tokens: list[dict] = Field(default_factory=list)

    # S6: Chunkify blocks (with section paths)
    chunks: list[dict] = Field(default_factory=list)

    # S8: Tagging
    tagged_chunks: list[dict] = Field(default_factory=list)

    # S9: Persist document
    document_id: str | None = None

    # S10: Persist chunks
    chunk_ids: list[str] = Field(default_factory=list)

    # S11: Update FTS
    fts_updated: bool = False
