from pathlib import Path

from common.utils.parsers import extract_document_date

HELIX_FILE = (
    Path(__file__).parent.parent
    / ".data"
    / "ingest"
    / "Затейчук_В_Е_04_06_2026_Общий анализ мочи-helix-lab-minimax.md"
)


def test_helix_lab_file_uses_validation_date_fallback() -> None:
    """Helix reports only have Дата заказа/валидации — validation wins in fallback pass."""
    if not HELIX_FILE.exists():
        content = (
            "- **Дата рождения:** 23.02.1971\n"
            "- **Дата заказа:** 03.06.2026 12:05\n"
            "- **Дата валидации:** 03.06.2026 18:06\n"
        )
    else:
        content = HELIX_FILE.read_text(encoding="utf-8")

    assert extract_document_date(content) == "2026-06-03"
