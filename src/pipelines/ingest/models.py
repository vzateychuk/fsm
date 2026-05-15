from dataclasses import dataclass
from typing import TypedDict

from pydantic import Field

from fsm.models import SagaData, SagaInput


class IngestInput(SagaInput):
    """Input data for ingest pipeline"""

    source_path: str


@dataclass(slots=True)
class MdToken:
    """Markdown token from markdown-it-py parser

    Attributes:
        type: token type (heading, paragraph, table, list, fence)
        content: plain text content (inline markup removed, serialized if complex)
        level: heading level (1-6 for H1-H6), 0 for other types
        markup: markup hint (e.g., '#' for headings, language for fence)
    """
    type: str
    content: str
    level: int = 0
    markup: str = ""


class BlockEvent(TypedDict):
    """Event from BuildSectionPath step

    Fields:
        token: MdToken produced by parser
        section_path: breadcrumb path (e.g., "H1 > H2")
        heading: last heading in path or None
    """
    token: MdToken
    section_path: str
    heading: str | None


class Chunk(TypedDict):
    """Chunk after ChunkifyBlocks and Tagging

    Fields:
        kind: semantic type (section, table, list, fact)
        text: chunk text content
        section_path: hierarchical breadcrumb
        heading: parent heading or None
        chunk_no: sequential number within document
        tags_text: space-separated deduplicated tags
    """
    kind: str
    text: str
    section_path: str
    heading: str | None
    chunk_no: int
    tags_text: str


class IngestData(SagaData):
    """Pipeline state data with field contracts per Phase 0.1

    Field invariants (guaranteed after respective step):
    - S0 LoadSource: raw_content (not None, full file text)
    - S1 PreprocessText: file_hash (not None, 64 hex chars)
    - S2 DetectTargetSchema: target_schema (not None, in {lab, diagnostic, consultation})
    - S3 SplitControlBlocks: metadata_block (may be None), md_body (not None, no schema line)
    - S4 ParseToTokens: tokens (may be empty, E_MD_PARSE_FAIL on parser error)
    - S5 BuildSectionPath: block_events (all blocks with section_path and heading)
    - S6 ChunkifyBlocks: chunks (len >= 1, E_EMPTY_CHUNKS if empty)
    - S7 Tagging: tagged_chunks (len == len(chunks), tags_text not empty)
    - S8 PersistDocument: document_id (not None, deterministic from file_hash[:32])
    - S9 PersistChunks: chunk_ids (len == len(tagged_chunks))
    - S10 UpdateFTS: fts_updated (always True after step)
    """

    desc: str | None = None

    # S0 LoadSource
    raw_content: str | None = None

    # S1 PreprocessText
    file_hash: str | None = None

    # S2 DetectTargetSchema
    target_schema: str | None = None

    # S3 SplitControlBlocks
    metadata_block: str | None = None
    md_body: str | None = None

    # S4 ParseToTokens
    tokens: list[MdToken] = Field(default_factory=list)

    # S5 BuildSectionPath
    block_events: list[BlockEvent] = Field(default_factory=list)

    # S6 ChunkifyBlocks
    chunks: list[Chunk] = Field(default_factory=list)

    # S7 Tagging
    tagged_chunks: list[Chunk] = Field(default_factory=list)

    # S8 PersistDocument
    document_id: str | None = None

    # S9 PersistChunks
    chunk_ids: list[str] = Field(default_factory=list)

    # S10 UpdateFTS
    fts_updated: bool = False


class IngestError(Exception):
    """Domain error for ingest pipeline with error code tracking

    Codes:
        E_READ_FAIL: file read failed (transient)
        E_DB_FAIL: database operation failed (transient)
        E_NO_SCHEMA_ID: Target Schema ID not found (fatal)
        E_SCHEMA_INVALID: Target Schema ID value not in {lab, diagnostic, consultation} (fatal)
        E_MD_PARSE_FAIL: markdown parsing failed (fatal)
        E_EMPTY_CHUNKS: no chunks produced (fatal)
    """
    def __init__(self, code: str, message: str = ""):
        self.code = code
        self.message = message or code
        super().__init__(f"{code}: {message}")
