"""Unit tests for fts_query: sanitize_fts_term and build_fts_match."""

from __future__ import annotations

import pytest

from pipelines.retrieval.config import RetrievalConfig
from pipelines.retrieval.fts_query import build_fts_match, sanitize_fts_term


@pytest.fixture
def cfg() -> RetrievalConfig:
    return RetrievalConfig(enable_prefixes=True, prefix_min_len=5)


@pytest.fixture
def cfg_no_prefix() -> RetrievalConfig:
    return RetrievalConfig(enable_prefixes=False, prefix_min_len=5)


# ---------------------------------------------------------------------------
# sanitize_fts_term
# ---------------------------------------------------------------------------


class TestSanitizeFtsTerm:
    def test_plain_cyrillic_unchanged(self) -> None:
        assert sanitize_fts_term("протрузия") == "протрузия"

    def test_plain_latin_unchanged(self) -> None:
        assert sanitize_fts_term("pth") == "pth"

    def test_empty_returns_empty(self) -> None:
        assert sanitize_fts_term("") == ""

    def test_space_triggers_quoting(self) -> None:
        assert sanitize_fts_term("h. pylori") == '"h. pylori"'

    def test_internal_double_quote_escaped(self) -> None:
        assert sanitize_fts_term('say "hello"') == '"say ""hello"""'

    def test_parenthesis_triggers_quoting(self) -> None:
        assert sanitize_fts_term("a(b)") == '"a(b)"'

    def test_asterisk_triggers_quoting(self) -> None:
        assert sanitize_fts_term("term*") == '"term*"'

    def test_hyphen_triggers_quoting(self) -> None:
        assert sanitize_fts_term("anti-aging") == '"anti-aging"'


# ---------------------------------------------------------------------------
# build_fts_match
# ---------------------------------------------------------------------------


class TestBuildFtsMatch:
    def test_empty_list_returns_empty(self, cfg: RetrievalConfig) -> None:
        assert build_fts_match([], cfg) == ""

    def test_single_short_cyrillic_no_prefix(self, cfg: RetrievalConfig) -> None:
        # "мрт" has len=3 < prefix_min_len=5 — no wildcard
        assert build_fts_match(["мрт"], cfg) == "мрт"

    def test_single_long_cyrillic_gets_prefix(self, cfg: RetrievalConfig) -> None:
        # "протрузия" has len=9 >= 5, all Cyrillic — wildcard appended
        assert build_fts_match(["протрузия"], cfg) == "протрузия*"

    def test_cyrillic_exactly_min_len_gets_prefix(self, cfg: RetrievalConfig) -> None:
        # "кровь" has len=5 == prefix_min_len — wildcard appended
        assert build_fts_match(["кровь"], cfg) == "кровь*"

    def test_latin_term_no_prefix(self, cfg: RetrievalConfig) -> None:
        # Latin terms never get a prefix wildcard
        assert build_fts_match(["pth"], cfg) == "pth"

    def test_phrase_with_space_is_quoted(self, cfg: RetrievalConfig) -> None:
        assert build_fts_match(["h. pylori"], cfg) == '"h. pylori"'

    def test_multiple_terms_joined_with_or(self, cfg: RetrievalConfig) -> None:
        result = build_fts_match(["птг", "pth"], cfg)
        assert result == "птг OR pth"

    def test_mixed_terms_or_joined_with_prefix(self, cfg: RetrievalConfig) -> None:
        result = build_fts_match(["мрт", "протрузия", "pth"], cfg)
        assert result == "мрт OR протрузия* OR pth"

    def test_prefixes_disabled(self, cfg_no_prefix: RetrievalConfig) -> None:
        # Long Cyrillic terms must not get wildcard when enable_prefixes=False
        assert build_fts_match(["протрузия"], cfg_no_prefix) == "протрузия"

    def test_empty_string_in_list_skipped(self, cfg: RetrievalConfig) -> None:
        # Empty strings inside the list are filtered out
        assert build_fts_match(["", "мрт", ""], cfg) == "мрт"
