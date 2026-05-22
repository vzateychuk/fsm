"""Unit tests for KBContextBundleBuilder."""

import pytest

from src.pipelines.consult.bundle_builder import KBContextBundleBuilder
from src.pipelines.consult.config import ConsultConfig
from src.store.knowledge_store import ChunkSearchResult


def make_chunk(
    chunk_id: str,
    document_id: str = "doc1",
    chunk_no: int = 0,
    text: str = "test",
    category: str = "Test",
    rank: float = 1.0,
) -> ChunkSearchResult:
    """Helper to create a ChunkSearchResult."""
    return ChunkSearchResult(
        chunk_id=chunk_id,
        document_id=document_id,
        chunk_no=chunk_no,
        kind="fact",
        text=text,
        section_path=None,
        heading=None,
        tags_text=None,
        source_path="test.md",
        category=category,
        rank=rank,
    )


def test_deduplication_query_priority():
    """Query chunks take priority over recency chunks with same chunk_id."""
    config = ConsultConfig.load("config/consult.yaml")
    builder = KBContextBundleBuilder(config)

    query_chunks = [
        make_chunk("c1", text="query version"),
        make_chunk("c2", text="only in query"),
    ]
    recency_chunks = [
        make_chunk("c1", text="recency version"),  # duplicate id
        make_chunk("c3", text="only in recency"),
    ]

    result = builder.build(query_chunks, recency_chunks)

    all_excerpts = result.top_chunks + result.kb_excerpts
    assert len(all_excerpts) == 3
    assert all_excerpts[0] == "query version"
    assert all_excerpts[1] == "only in query"
    assert all_excerpts[2] == "only in recency"


def test_max_total_chunks_limit():
    """Bundle respects max_total_chunks limit."""
    config = ConsultConfig.load("config/consult.yaml")
    builder = KBContextBundleBuilder(config)

    query_chunks = [make_chunk(f"c{i}", text=f"chunk {i}") for i in range(10)]
    recency_chunks = [make_chunk(f"c{10+i}", text=f"chunk {10+i}") for i in range(10)]

    result = builder.build(query_chunks, recency_chunks)

    total_chunks = len(result.top_chunks) + len(result.kb_excerpts)
    assert total_chunks <= config.bundle.max_total_chunks


def test_max_total_chars_applied_after_truncation():
    """max_total_chars limit is enforced AFTER line truncation."""
    config = ConsultConfig.load("config/consult.yaml")
    builder = KBContextBundleBuilder(config)

    long_text = "\n".join([f"line {i}" for i in range(100)])
    query_chunks = [make_chunk("c1", text=long_text, category="Unknown")]

    result = builder.build(query_chunks, [])

    total_chars = sum(len(text) for text in result.kb_excerpts)
    assert total_chars <= config.bundle.max_total_chars


def test_full_text_categories_no_truncation():
    """full_text_categories are not truncated (full text preserved)."""
    config = ConsultConfig.load("config/consult.yaml")
    builder = KBContextBundleBuilder(config)

    long_text = "\n".join([f"line {i}" for i in range(100)])
    query_chunks = [
        make_chunk(f"c{i}", text=f"short chunk {i}") for i in range(config.excerpts.top_chunks_count + 3)
    ]
    query_chunks.append(make_chunk("full_consult", text=long_text, category="Консультация"))

    result = builder.build(query_chunks, [])

    bundle_text = result.kb_excerpts[-1]  # Last kb_excerpts is the long one
    lines = bundle_text.split("\n")
    assert len(lines) == 100  # full_text_categories not truncated


def test_category_line_limits_applied():
    """category_line_limits are enforced for specific categories."""
    config = ConsultConfig.load("config/consult.yaml")
    builder = KBContextBundleBuilder(config)

    long_text = "\n".join([f"line {i}" for i in range(100)])
    query_chunks = [
        make_chunk(f"c{i}", text=f"short chunk {i}") for i in range(config.excerpts.top_chunks_count + 3)
    ]
    query_chunks.append(make_chunk("diag", text=long_text, category="Диагноз"))

    result = builder.build(query_chunks, [])

    bundle_text = result.kb_excerpts[-1]  # Last kb_excerpts is the long one
    lines = bundle_text.split("\n")
    assert len(lines) == config.excerpts.category_line_limits["Диагноз"]


def test_max_lines_default_for_unknown_category():
    """Unknown categories use max_lines_default."""
    config = ConsultConfig.load("config/consult.yaml")
    builder = KBContextBundleBuilder(config)

    long_text = "\n".join([f"line {i}" for i in range(100)])
    query_chunks = [
        make_chunk(f"c{i}", text=f"short chunk {i}") for i in range(config.excerpts.top_chunks_count + 3)
    ]
    query_chunks.append(make_chunk("unknown", text=long_text, category="UnknownCategory"))

    result = builder.build(query_chunks, [])

    bundle_text = result.kb_excerpts[-1]  # Last kb_excerpts is the long one
    lines = bundle_text.split("\n")
    assert len(lines) == config.excerpts.max_lines_default


def test_top_chunks_come_first():
    """Top chunks are formatted separately and come first."""
    config = ConsultConfig.load("config/consult.yaml")
    builder = KBContextBundleBuilder(config)

    query_chunks = [make_chunk(f"c{i}", text=f"chunk {i}") for i in range(10)]

    result = builder.build(query_chunks, [])

    assert len(result.top_chunks) == min(config.excerpts.top_chunks_count, 10)
    assert len(result.kb_excerpts) == max(0, 10 - config.excerpts.top_chunks_count)
    assert len(result.top_chunks) + len(result.kb_excerpts) == 10


def test_top_chunks_truncated_to_lines():
    """Top chunks are truncated to top_chunks_lines."""
    config = ConsultConfig.load("config/consult.yaml")
    builder = KBContextBundleBuilder(config)

    long_text = "\n".join([f"line {i}" for i in range(20)])
    query_chunks = [make_chunk("c1", text=long_text)]

    result = builder.build(query_chunks, [])

    top_chunk_lines = result.top_chunks[0].split("\n")
    assert len(top_chunk_lines) == config.excerpts.top_chunks_lines


def test_provenance_format():
    """Provenance entries follow format: doc_id | source_path | section_path."""
    config = ConsultConfig.load("config/consult.yaml")
    builder = KBContextBundleBuilder(config)

    chunks = [make_chunk(f"c{i}", text=f"short {i}") for i in range(config.excerpts.top_chunks_count)]
    chunk_with_section = ChunkSearchResult(
        chunk_id="c_with_section",
        document_id="doc2",
        chunk_no=0,
        kind="fact",
        text="text in kb_excerpts",
        section_path="section/subsection",
        heading=None,
        tags_text=None,
        source_path="file.md",
        category="Test",
        rank=0.0,
    )
    chunks.append(chunk_with_section)

    result = builder.build(chunks, [])

    assert len(result.provenance) == 1
    assert "doc2" in result.provenance[0]
    assert "file.md" in result.provenance[0]
    assert "section/subsection" in result.provenance[0]


def test_empty_input():
    """Empty input results in empty bundle (no exceptions)."""
    config = ConsultConfig.load("config/consult.yaml")
    builder = KBContextBundleBuilder(config)

    result = builder.build([], [])

    assert len(result.top_chunks) == 0
    assert len(result.kb_excerpts) == 0
    assert len(result.provenance) == 0


def test_multiple_categories_mixed():
    """Mixed categories are handled correctly."""
    config = ConsultConfig.load("config/consult.yaml")
    builder = KBContextBundleBuilder(config)

    long_text = "\n".join([f"line {i}" for i in range(100)])
    query_chunks = [
        make_chunk(f"c{i}", text=f"short {i}") for i in range(config.excerpts.top_chunks_count)
    ]
    query_chunks.extend([
        make_chunk("c_consult", text=long_text, category="Консультация"),  # full text
        make_chunk("c_analiz", text=long_text, category="Анализы"),  # 60 lines
        make_chunk("c_unknown", text=long_text, category="Unknown"),  # 20 lines (default)
    ])

    result = builder.build(query_chunks, [])

    assert len(result.kb_excerpts[0].split("\n")) == 100  # Консультация - full text
    assert len(result.kb_excerpts[1].split("\n")) == 60   # Анализы - 60 lines
    assert len(result.kb_excerpts[2].split("\n")) == 20   # Unknown - 20 lines (default)
