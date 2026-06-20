"""Unit tests for ChunkifyBlocks S6 — admin-section detection and kind=meta assignment."""

from __future__ import annotations

import sys
from pathlib import Path

# Add src to path before any imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import pytest

from fsm.core import RunContext
from pipelines.ingest.models import BlockEvent, IngestData, IngestInput, MdToken
from pipelines.ingest.steps.chunkify_blocks import ChunkifyBlocks, _is_admin_heading

ADMIN_HEADINGS: frozenset[str] = frozenset([
    "информация о пациенте",
    "сведения об обследовании",
    "аббревиатуры",
    "пациент",
])


def _make_ctx(events: list[BlockEvent], extra_tokens: int = 1) -> RunContext[IngestInput, IngestData]:
    """Build a minimal RunContext with the given block_events.

    extra_tokens adds padding to satisfy assert_block_events invariant:
    len(block_events) <= len(tokens).
    """
    padding = [MdToken(type="heading", content="Заголовок", level=2)] * extra_tokens
    block_tokens = [e["token"] for e in events]
    data = IngestData(
        block_events=events,
        tokens=padding + block_tokens,
    )
    return RunContext(
        run_id="test",
        saga_name="test",
        cursor=0,
        input=IngestInput(source_path="test.md"),
        data=data,
    )


class TestIsAdminHeading:
    def test_exact_lowercase_match(self) -> None:
        assert _is_admin_heading("информация о пациенте", ADMIN_HEADINGS) is True

    def test_mixed_case_match(self) -> None:
        assert _is_admin_heading("Информация о Пациенте", ADMIN_HEADINGS) is True

    def test_uppercase_match(self) -> None:
        assert _is_admin_heading("АББРЕВИАТУРЫ", ADMIN_HEADINGS) is True

    def test_yo_normalized_to_ye(self) -> None:
        # ё → е normalization: normalize_text converts ё→е, so "Свёдения об обслёдовании" matches
        assert _is_admin_heading("Свёдения об обслёдовании", ADMIN_HEADINGS) is True
        # Exact match also works
        assert _is_admin_heading("Сведения об обследовании", ADMIN_HEADINGS) is True

    def test_non_admin_heading(self) -> None:
        assert _is_admin_heading("Жалобы и анамнез", ADMIN_HEADINGS) is False

    def test_none_heading(self) -> None:
        assert _is_admin_heading(None, ADMIN_HEADINGS) is False

    def test_empty_string_heading(self) -> None:
        assert _is_admin_heading("", ADMIN_HEADINGS) is False

    def test_partial_match_not_accepted(self) -> None:
        assert _is_admin_heading("информация", ADMIN_HEADINGS) is False


class TestChunkifyBlocksMetaKind:
    async def test_admin_heading_produces_meta_kind(self) -> None:
        step = ChunkifyBlocks(max_section_chars=4000, admin_headings=ADMIN_HEADINGS)
        token = MdToken(type="paragraph", content="Возраст: 35 лет. Пол: женский.", level=0)
        events: list[BlockEvent] = [
            {
                "token": token,
                "section_path": "документ > информация о пациенте",
                "heading": "Информация о пациенте",
            }
        ]
        ctx = _make_ctx(events)

        await step.run(ctx)

        assert len(ctx.data.chunks) == 1
        assert ctx.data.chunks[0]["kind"] == "meta"

    async def test_clinical_heading_keeps_section_kind(self) -> None:
        step = ChunkifyBlocks(max_section_chars=4000, admin_headings=ADMIN_HEADINGS)
        token = MdToken(type="paragraph", content="Боль в животе справа, острая.", level=0)
        events: list[BlockEvent] = [
            {
                "token": token,
                "section_path": "документ > жалобы и анамнез",
                "heading": "Жалобы и анамнез",
            }
        ]
        ctx = _make_ctx(events)

        await step.run(ctx)

        assert len(ctx.data.chunks) == 1
        assert ctx.data.chunks[0]["kind"] == "section"

    async def test_list_token_in_admin_section_gets_meta(self) -> None:
        step = ChunkifyBlocks(max_section_chars=4000, admin_headings=ADMIN_HEADINGS)
        token = MdToken(type="list", content="- Сокращение 1\n- Сокращение 2", level=0)
        events: list[BlockEvent] = [
            {
                "token": token,
                "section_path": "документ > аббревиатуры",
                "heading": "Аббревиатуры",
            }
        ]
        ctx = _make_ctx(events)

        await step.run(ctx)

        assert ctx.data.chunks[0]["kind"] == "meta"

    async def test_short_patient_heading_gets_meta(self) -> None:
        step = ChunkifyBlocks(max_section_chars=4000, admin_headings=ADMIN_HEADINGS)
        token = MdToken(type="list", content="- **Пациент:** Ivanov", level=0)
        events: list[BlockEvent] = [
            {
                "token": token,
                "section_path": "orthopedist consultation > пациент",
                "heading": "пациент",
            }
        ]
        ctx = _make_ctx(events)

        await step.run(ctx)

        assert ctx.data.chunks[0]["kind"] == "meta"

    async def test_empty_admin_headings_leaves_kind_unchanged(self) -> None:
        step = ChunkifyBlocks(max_section_chars=4000, admin_headings=frozenset())
        token = MdToken(type="paragraph", content="Возраст: 35 лет.", level=0)
        events: list[BlockEvent] = [
            {
                "token": token,
                "section_path": "документ > информация о пациенте",
                "heading": "Информация о пациенте",
            }
        ]
        ctx = _make_ctx(events)

        await step.run(ctx)

        assert ctx.data.chunks[0]["kind"] == "section"

    async def test_mixed_events_correct_kinds(self) -> None:
        """Clinical and admin sections in the same document — each gets correct kind."""
        step = ChunkifyBlocks(max_section_chars=4000, admin_headings=ADMIN_HEADINGS)
        clinical_token = MdToken(type="paragraph", content="Острая боль в правом подреберье.", level=0)
        admin_token = MdToken(type="paragraph", content="Возраст: 42. Пол: мужской.", level=0)
        events: list[BlockEvent] = [
            {
                "token": clinical_token,
                "section_path": "документ > жалобы",
                "heading": "Жалобы",
            },
            {
                "token": admin_token,
                "section_path": "документ > информация о пациенте",
                "heading": "Информация о пациенте",
            },
        ]
        ctx = _make_ctx(events)

        await step.run(ctx)

        assert len(ctx.data.chunks) == 2
        kinds = {c["heading"]: c["kind"] for c in ctx.data.chunks}
        assert kinds["Жалобы"] == "section"
        assert kinds["Информация о пациенте"] == "meta"
