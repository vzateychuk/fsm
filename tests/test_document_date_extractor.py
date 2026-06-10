"""Tests for extract_document_date utility - content-based date extraction."""
from pathlib import Path

from common.utils.parsers import DocumentDateSuffixConfig, extract_document_date


class TestExtractFromContent:
    """Priority 1: markdown markers in document header"""

    def test_iso_format_with_bullet(self) -> None:
        content = "- **Дата:** 2023-02-24\n"
        assert extract_document_date(content) == "2023-02-24"

    def test_iso_format_with_asterisk_bullet(self) -> None:
        content = "* **Дата:** 2023-02-24\n"
        assert extract_document_date(content) == "2023-02-24"

    def test_iso_format_no_bullet(self) -> None:
        content = "**Дата:** 2020-02-09\n"
        assert extract_document_date(content) == "2020-02-09"

    def test_dd_mm_yyyy_format_normalized(self) -> None:
        content = "- **Дата приема:** 04.11.2023\n"
        assert extract_document_date(content) == "2023-11-04"

    def test_date_issledovaniya(self) -> None:
        content = "- **Дата исследования:** 05.06.2025\n"
        assert extract_document_date(content) == "2025-06-05"

    def test_date_konsultacii(self) -> None:
        content = "- **Дата консультации:** 11.01.2023\n"
        assert extract_document_date(content) == "2023-01-11"

    def test_date_i_vremya_priema(self) -> None:
        content = "- **Дата и время приема:** 10.03.2024, 13:40\n"
        assert extract_document_date(content) == "2024-03-10"

    def test_skip_birth_date(self) -> None:
        """Дата рождения is the patient's birth date, NOT the document date."""
        content = "- **Дата рождения:** 23.02.1971\n- **Дата исследования:** 17.09.2019\n"
        assert extract_document_date(content) == "2019-09-17"

    def test_skip_birth_date_iso(self) -> None:
        content = "- **Дата рождения:** 1971-02-23\n- **Дата:** 2015-11-16\n"
        assert extract_document_date(content) == "2015-11-16"

    def test_skip_validation_date(self) -> None:
        """Дата валидации is a secondary timestamp, prefer Дата анализа."""
        content = (
            "- **Дата анализа:** 2024-09-11\n"
            "- **Дата валидации:** 2024-09-12\n"
        )
        assert extract_document_date(content) == "2024-09-11"

    def test_first_match_wins(self) -> None:
        # When multiple valid dates exist, first one in header wins.
        content = (
            "- **Дата:** 2023-02-23\n"
            "- **Дата исследования:** 2023-02-24\n"
        )
        assert extract_document_date(content) == "2023-02-23"


class TestExtractFromYamlMetadata:
    """Priority 2: YAML frontmatter (fallback)"""

    def test_yaml_date_key(self) -> None:
        content = "---\ndate: 2025-06-15\n---\n\n# Title\n"
        assert extract_document_date(content) == "2025-06-15"

    def test_yaml_document_date_key(self) -> None:
        content = "---\ndocument_date: 2025-06-15\n---\n\n# Title\n"
        assert extract_document_date(content) == "2025-06-15"

    def test_yaml_visit_date_key(self) -> None:
        content = "---\nvisit_date: 2025-06-15\n---\n\n# Title\n"
        assert extract_document_date(content) == "2025-06-15"

    def test_malformed_yaml_returns_none(self) -> None:
        content = "---\ndate: [invalid : yaml\n---\n"
        assert extract_document_date(content) is None

    def test_unterminated_yaml_block_returns_none(self) -> None:
        content = "---\ndate: 2025-06-15\nno closing marker\n"
        assert extract_document_date(content) is None


class TestNoDate:
    """No date extractable from content -> None"""

    def test_empty_inputs(self) -> None:
        assert extract_document_date("") is None

    def test_no_date_anywhere(self) -> None:
        content = "# Title\n\nSome content without any date markers.\n"
        assert extract_document_date(content) is None

    def test_only_birth_date_in_content(self) -> None:
        # Single hard-excluded marker should not match.
        content = "- **Дата рождения:** 23.02.1971\n"
        assert extract_document_date(content) is None

    def test_order_date_used_as_fallback_when_no_preferred(self) -> None:
        content = (
            "- **Дата рождения:** 23.02.1971\n"
            "- **Дата заказа:** 04.06.2026 12:05\n"
        )
        assert extract_document_date(content) == "2026-06-04"

    def test_validation_date_preferred_over_order_date_in_fallback(self) -> None:
        content = (
            "- **Дата заказа:** 03.06.2026 12:05\n"
            "- **Дата валидации:** 04.06.2026 18:06\n"
        )
        assert extract_document_date(content) == "2026-06-04"

    def test_empty_fallback_list_falls_through_to_filename(self) -> None:
        """When fallback disabled and order/validation hard-excluded, filename is used."""
        no_fallback = DocumentDateSuffixConfig(
            hard_excluded=("рождения", "отправки", "печати", "заказа", "валидации"),
            fallback=(),
            filename_patterns=("^(\\d{4}-\\d{2}-\\d{2})[_\\-]",),
        )
        content = "- **Дата заказа:** 15.03.2024\n- **Дата рождения:** 23.02.1971\n"
        assert extract_document_date(
            content,
            source_path=Path("2024-10-13_lab-panel.md"),
            date_config=no_fallback,
        ) == "2024-10-13"

    def test_filename_not_used_without_source_path(self) -> None:
        """Without source_path argument filename extraction is skipped -> None."""
        assert extract_document_date("") is None


class TestExtractFromFilename:
    """Priority 3: YYYY-MM-DD prefix in filename stem."""

    def test_underscore_separator(self) -> None:
        assert extract_document_date("", source_path=Path("2024-10-13_lab-panel.md")) == "2024-10-13"

    def test_dash_separator(self) -> None:
        assert extract_document_date("", source_path=Path("2024-10-13-lab-panel.md")) == "2024-10-13"

    def test_source_path_as_string(self) -> None:
        assert extract_document_date("", source_path="2024-10-13_report.md") == "2024-10-13"

    def test_full_path(self) -> None:
        assert extract_document_date("", source_path=Path("/data/ingest/2024-10-13_lab-panel.md")) == "2024-10-13"

    def test_no_date_prefix_returns_none(self) -> None:
        assert extract_document_date("", source_path=Path("lab-panel.md")) is None

    def test_source_path_none_returns_none(self) -> None:
        assert extract_document_date("", source_path=None) is None

    def test_content_takes_priority_over_filename(self) -> None:
        content = "- **Дата исследования:** 15.03.2024\n"
        assert extract_document_date(content, source_path=Path("2024-10-13_lab-panel.md")) == "2024-03-15"

    def test_order_date_used_when_no_preferred_date(self) -> None:
        # Дата заказа is fallback when no preferred date marker exists
        content = "- **Дата заказа:** 15.03.2024\n- **Дата рождения:** 23.02.1971\n"
        assert extract_document_date(content, source_path=Path("2024-10-13_lab-panel.md")) == "2024-03-15"

    def test_filename_suffix_yyyymmdd(self) -> None:
        assert extract_document_date(
            "# Title\n",
            source_path=Path("helix-lab-blood-minimax-20260604.md"),
        ) == "2026-06-04"
