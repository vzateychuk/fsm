"""Field guards and invariant checks — ensures data contract is maintained."""

from typing import Any

from pipelines.ingest.models import BlockEvent, ChunkBase, IngestData

# Invariant contract from Phase 0.1
INVARIANTS: dict[str, list[str]] = {
    "load_source": ["raw_content"],
    "preprocess_text": ["raw_content", "file_hash"],
    "detect_target_schema": ["target_schema"],
    "split_control_blocks": ["md_body"],
    "parse_to_tokens": ["tokens"],
    "build_section_path": ["block_events"],
    "chunkify_blocks": ["chunks"],
    "tagging": ["tagged_chunks"],
    "persist_source_file": ["filestore_path"],
    "persist_document": ["document_id"],
    "persist_chunks": ["chunk_ids", "fts_updated"],
}


def assert_field(value: Any, field_name: str, required_by_step: str) -> None:
    """Raise RuntimeError if value is None, indicating missing dependency."""
    if value is None:
        raise RuntimeError(
            f"Field '{field_name}' is None. "
            f"This step requires it to be filled by '{required_by_step}' first."
        )


def assert_raw_content(ctx_data: IngestData, current_step: str) -> str:
    """Ensure raw_content is available; raise if missing."""
    assert_field(ctx_data.raw_content, "raw_content", "LoadSource")
    assert ctx_data.raw_content is not None
    return ctx_data.raw_content


def assert_md_body(ctx_data: IngestData, current_step: str) -> str:
    """Ensure md_body is available; raise if missing."""
    assert_field(ctx_data.md_body, "md_body", "SplitControlBlocks")
    assert ctx_data.md_body is not None
    return ctx_data.md_body


def assert_file_hash(ctx_data: IngestData, current_step: str) -> str:
    """Ensure file_hash is available; raise if missing."""
    assert_field(ctx_data.file_hash, "file_hash", "PreprocessText")
    assert ctx_data.file_hash is not None
    return ctx_data.file_hash


def assert_tokens(ctx_data: IngestData, current_step: str) -> list[Any]:
    """Ensure tokens list is available; raise if missing."""
    assert_field(ctx_data.tokens, "tokens", "ParseToTokens")
    assert ctx_data.tokens is not None
    return ctx_data.tokens


def assert_block_events(ctx_data: IngestData, current_step: str) -> list[BlockEvent]:
    """Ensure block_events list is available and valid; raise if missing or malformed.

    Invariants:
    - block_events is not None
    - len(block_events) > 0 (non-empty; empty block_events → E_EMPTY_CHUNKS later)
    - Each event has: token (non-heading), section_path (may be ""), heading (may be None)
    - Order matches original non-heading blocks from tokens
    """
    assert_field(ctx_data.block_events, "block_events", "BuildSectionPath")
    assert ctx_data.block_events is not None

    if len(ctx_data.block_events) > len(ctx_data.tokens):
        raise AssertionError(
            f"block_events count {len(ctx_data.block_events)} > tokens count {len(ctx_data.tokens)}. "
            f"BuildSectionPath should only emit non-heading tokens."
        )

    for i, event in enumerate(ctx_data.block_events):
        if event.get("token") is None:
            raise AssertionError(f"block_events[{i}] missing 'token' field")
        if "section_path" not in event:
            raise AssertionError(f"block_events[{i}] missing 'section_path' field")
        if "heading" not in event:
            raise AssertionError(f"block_events[{i}] missing 'heading' field")
        # Verify token is not a heading (only non-heading tokens in block_events)
        if event["token"].type == "heading":
            raise AssertionError(f"block_events[{i}] contains heading token; only non-heading allowed")

    return ctx_data.block_events


def assert_filestore_path(ctx_data: IngestData, current_step: str) -> str:
    """Ensure filestore_path is available; raise if missing."""
    assert_field(ctx_data.filestore_path, "filestore_path", "PersistSourceFile")
    assert ctx_data.filestore_path is not None
    return ctx_data.filestore_path


def assert_document_id(ctx_data: IngestData, current_step: str) -> str:
    """Ensure document_id is available; raise if missing."""
    assert_field(ctx_data.document_id, "document_id", "PersistDocument")
    assert ctx_data.document_id is not None
    return ctx_data.document_id


def assert_chunks(ctx_data: IngestData, current_step: str) -> list[ChunkBase]:
    """Ensure chunks list is available; raise if missing."""
    assert_field(ctx_data.chunks, "chunks", "ChunkifyBlocks")
    assert ctx_data.chunks is not None
    return ctx_data.chunks


def assert_invariants(data: IngestData, after_step: str) -> None:
    """
    Validate data contract after a step completes.

    Checks that all fields required by the step are non-None.
    Called in debug/test mode only — not in production.

    Args:
        data: IngestData object
        after_step: step id (e.g., "load_source", "preprocess_text")

    Raises:
        AssertionError if any required field is None
    """
    if after_step not in INVARIANTS:
        return  # Unknown step, skip check

    required_fields = INVARIANTS[after_step]
    for field_name in required_fields:
        value = getattr(data, field_name, None)
        if value is None or (isinstance(value, (list, str)) and not value):
            raise AssertionError(
                f"After step '{after_step}': field '{field_name}' is empty/None. "
                f"This violates the data contract."
            )
