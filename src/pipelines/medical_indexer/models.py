from fsm.models import SagaInput, SagaData


class MedDocInput(SagaInput):
    """Входные данные для medical indexer pipeline"""

    source_path: str


class MedDocData(SagaData):
    """Данные для medical indexer pipeline"""

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
    tokens: list[dict] = []

    # S6: Build section path
    section_path: list[str] = []

    # S7: Chunkify blocks
    chunks: list[dict] = []

    # S8: Tagging
    tagged_chunks: list[dict] = []

    # S9: Persist document
    document_id: str | None = None

    # S10: Persist chunks
    chunk_ids: list[str] = []

    # S11: Update FTS
    fts_updated: bool = False
