"""Tests for query tokenization."""

import pytest

from src.common.normalizer import tokenize_query


class TestTokenizeQuery:
    """Test tokenize_query function."""

    def test_removes_punctuation_and_pure_numbers(self) -> None:
        """Punctuation removed and pure numeric tokens filtered."""
        result = tokenize_query("болит живот справа, температура 37.8")
        # "37.8" becomes "37" and "8" after punctuation removal, both are pure numbers so filtered
        assert result == ["болит", "живот", "справа", "температура"]

    def test_splits_by_whitespace(self) -> None:
        """Should split by whitespace."""
        result = tokenize_query("экг электрокардиография")
        assert result == ["экг", "электрокардиография"]

    def test_removes_empty_tokens(self) -> None:
        """Empty tokens should be filtered out."""
        result = tokenize_query("болит  живот   справа")
        assert result == ["болит", "живот", "справа"]
        assert "" not in result

    def test_handles_various_punctuation(self) -> None:
        """Should remove various punctuation marks."""
        result = tokenize_query("результаты: 2.5 мг/дл; см примечание!")
        # Punctuation removed, "2" and "5" are pure numbers so filtered
        assert ":" not in " ".join(result)
        assert ";" not in " ".join(result)
        assert "!" not in " ".join(result)
        assert "2" not in result
        assert "5" not in result

    def test_filters_pure_numeric_tokens(self) -> None:
        """Pure numeric tokens should be filtered out."""
        result = tokenize_query("болит 37.8 живот 42 справа")
        # All pure numeric values are filtered
        assert result == ["болит", "живот", "справа"]
        assert "37" not in result
        assert "8" not in result
        assert "42" not in result

    def test_preserves_alphanumeric_tokens(self) -> None:
        """Tokens with letters AND numbers should be preserved."""
        result = tokenize_query("витамин B12 диагноз F41")
        # Mixed alphanumeric tokens are kept
        assert "витамин" in result
        assert "b12" in result
        assert "диагноз" in result
        assert "f41" in result

    def test_empty_query(self) -> None:
        """Empty query should return empty list."""
        result = tokenize_query("")
        assert result == []

    def test_only_punctuation_and_numbers(self) -> None:
        """Query with only punctuation and pure numbers returns empty list."""
        result = tokenize_query("!@#$%^&*() 123 456")
        assert result == []

    def test_pure_digits_filtered(self) -> None:
        """Pure numeric values should be filtered."""
        result = tokenize_query("37.8")
        # "37.8" becomes "37" and "8", both pure numbers, both filtered
        assert result == []
