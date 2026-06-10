from pathlib import Path

from common.normalizer import normalize_text
from common.utils.parsers import find_category, load_categories

HELIX_FILE = (
    Path(__file__).parent.parent.parent
    / ".data"
    / "ingest"
    / "Затейчук_В_Е_04_06_2026_Общий анализ мочи-helix-lab-minimax.md"
)


def test_helix_lab_file_category_detected() -> None:
    """Regression: Helix lab export uses '# Категория: Анализы' heading, not **Категория:**."""
    content = HELIX_FILE.read_text(encoding="utf-8")
    lines = normalize_text(content).split("\n")
    allowed = load_categories(Path("config/categories.yaml"))

    result = find_category(lines, allowed, search_limit=30)

    assert result is not None
    assert result.category == "Анализы"
    assert result.line_number == 0
    assert lines[0] == "# категория: анализы"
