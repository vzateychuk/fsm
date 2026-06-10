"""Test that extract_document_date handles all date key variants from real documents."""
from common.utils.parsers import extract_document_date


class TestAllDateKeyVariants:
    """Verify all common date key patterns are recognized."""

    def test_variant_data_priema_with_colon(self) -> None:
        """**Дата приема:** 10.03.2024"""
        content = "- **Дата приема:** 10.03.2024\n"
        assert extract_document_date(content) == "2024-03-10"

    def test_variant_data_issledovaniya_with_colon(self) -> None:
        """**Дата исследования:** 05.06.2025"""
        content = "- **Дата исследования:** 05.06.2025\n"
        assert extract_document_date(content) == "2025-06-05"

    def test_variant_data_simple_with_colon(self) -> None:
        """**Дата:** 2023-02-24 (ISO format)"""
        content = "**Дата:** 2023-02-24\n"
        assert extract_document_date(content) == "2023-02-24"

    def test_variant_data_simple_with_bullet_and_colon(self) -> None:
        """- **Дата:** 2023-02-24"""
        content = "- **Дата:** 2023-02-24\n"
        assert extract_document_date(content) == "2023-02-24"

    def test_variant_data_analiza_without_colon(self) -> None:
        """**Дата анализа** 2024-09-11 (no colon)"""
        content = "- **Дата анализа** 2024-09-11\n"
        assert extract_document_date(content) == "2024-09-11"

    def test_variant_data_analiza_with_colon(self) -> None:
        """**Дата анализа:** 2024-09-11 (with colon)"""
        content = "- **Дата анализа:** 2024-09-11\n"
        assert extract_document_date(content) == "2024-09-11"

    def test_variant_data_vypyski(self) -> None:
        """**Дата выписки** 2024-10-20 (no colon)"""
        content = "- **Дата выписки** 2024-10-20\n"
        assert extract_document_date(content) == "2024-10-20"

    def test_variant_data_vypyski_with_colon(self) -> None:
        """**Дата выписки:** 2024-10-20 (with colon)"""
        content = "- **Дата выписки:** 2024-10-20\n"
        assert extract_document_date(content) == "2024-10-20"

    def test_variant_data_konsultacii(self) -> None:
        """**Дата консультации:** 11.01.2023"""
        content = "- **Дата консультации:** 11.01.2023\n"
        assert extract_document_date(content) == "2023-01-11"

    def test_all_variants_together_first_wins(self) -> None:
        """When multiple date keys present, first one in header wins."""
        content = (
            "- **Дата:** 2023-01-01\n"
            "- **Дата исследования:** 2023-02-02\n"
            "- **Дата анализа:** 2023-03-03\n"
            "- **Дата выписки:** 2023-04-04\n"
            "- **Дата консультации:** 2023-05-05\n"
        )
        # First one wins
        assert extract_document_date(content) == "2023-01-01"

    def test_mixed_formats_in_different_keys(self) -> None:
        """Some keys use ISO, some use DD.MM.YYYY - all should work."""
        content = (
            "- **Дата:** 2023-02-24\n"
            "- **Дата исследования:** 05.06.2025\n"
        )
        # First match (ISO) wins
        assert extract_document_date(content) == "2023-02-24"

    def test_variant_with_extra_spaces(self) -> None:
        """Handle extra spaces in markup: ** Дата  анализа **"""
        content = "- **  Дата  анализа  ** 2024-09-11\n"
        assert extract_document_date(content) == "2024-09-11"


class TestExpandedFormats:
    """Test expanded date formats and markup variations."""

    def test_italic_markup_instead_of_bold(self) -> None:
        """*Дата исследования:* 15.03.2024 (italic instead of bold)"""
        content = "- *Дата исследования:* 15.03.2024\n"
        assert extract_document_date(content) == "2024-03-15"

    def test_italic_without_colon(self) -> None:
        """*Дата анализа* 2024-09-11 (italic, no colon)"""
        content = "- *Дата анализа* 2024-09-11\n"
        assert extract_document_date(content) == "2024-09-11"

    def test_date_with_slash_separator(self) -> None:
        """**Дата:** 15/03/2024 (slashes instead of dots)"""
        content = "**Дата:** 15/03/2024\n"
        assert extract_document_date(content) == "2024-03-15"

    def test_date_with_slash_and_time(self) -> None:
        """**Дата и время:** 15/03/2024 10:30 (slashes and time, time ignored)"""
        content = "**Дата и время:** 15/03/2024 10:30\n"
        assert extract_document_date(content) == "2024-03-15"

    def test_date_with_dot_and_time(self) -> None:
        """**Дата исследования:** 15.03.2024 14:25 (time component ignored)"""
        content = "- **Дата исследования:** 15.03.2024 14:25\n"
        assert extract_document_date(content) == "2024-03-15"

    def test_slash_iso_format_with_time(self) -> None:
        """2024-03-15 09:00 (ISO format with time, time stripped)"""
        content = "- **Дата:** 2024-03-15 09:00\n"
        assert extract_document_date(content) == "2024-03-15"

    def test_skip_order_date_when_preferred_present(self) -> None:
        """**Дата заказа:** skipped in pass 1 when **Дата анализа:** is present."""
        content = "- **Дата заказа:** 15.03.2024\n- **Дата анализа:** 20.03.2024\n"
        assert extract_document_date(content) == "2024-03-20"

    def test_skip_send_date(self) -> None:
        """**Дата отправки:** should be excluded (not document date)"""
        content = "- **Дата отправки:** 15.03.2024\n- **Дата исследования:** 10.03.2024\n"
        assert extract_document_date(content) == "2024-03-10"

    def test_skip_print_date(self) -> None:
        """**Дата печати:** should be excluded (not document date)"""
        content = "- **Дата:** 2024-03-15\n- **Дата печати:** 2024-03-16\n"
        assert extract_document_date(content) == "2024-03-15"

    def test_mixed_formats_with_various_separators(self) -> None:
        """Test priority when different formats coexist"""
        content = (
            "- **Дата:** 2024-03-10\n"
            "- **Дата исследования:** 15/03/2024\n"
            "- **Дата анализа:** 20.03.2024 11:00\n"
        )
        # First match (ISO) wins
        assert extract_document_date(content) == "2024-03-10"

    def test_italic_and_bold_together(self) -> None:
        """Mixed italic and bold markup"""
        content = (
            "- *Дата заказа:* 15.03.2024\n"
            "- **Дата исследования:** 20.03.2024\n"
        )
        # Bold wins (appears first after discarding заказа)
        assert extract_document_date(content) == "2024-03-20"
