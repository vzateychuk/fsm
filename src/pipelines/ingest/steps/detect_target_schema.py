from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar

from common.utils.parsers import find_category, load_categories
from fsm.core import RunContext
from pipelines.ingest.guards import assert_raw_content
from pipelines.ingest.models import IngestData, IngestError, IngestInput

_DEFAULT_CATEGORIES_CONFIG = Path(__file__).parents[4] / "config" / "categories.yaml"


@dataclass(slots=True)
class DetectTargetSchema:
    """S2: Detect document category from **Категория:** header line."""

    id: ClassVar[str] = "detect_target_schema"
    desc: ClassVar[str] = "Detect document category from header"

    categories_config: Path = field(default_factory=lambda: _DEFAULT_CATEGORIES_CONFIG)
    _allowed: list[str] = field(init=False)

    def __post_init__(self) -> None:
        self._allowed = load_categories(self.categories_config)

    async def run(self, ctx: RunContext[IngestInput, IngestData]) -> None:
        ctx.data.desc = self.desc
        content = assert_raw_content(ctx.data, self.id)
        lines = content.split("\n")

        match = find_category(lines, self._allowed, search_limit=30)
        if not match:
            raise IngestError("E_NO_SCHEMA_ID", "Категория not found or not in allowed list")

        ctx.data.target_schema = match.category
        ctx.data.desc = f"Category detected: {match.category}"
