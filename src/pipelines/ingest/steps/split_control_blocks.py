import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar

from common.utils.parsers import extract_document_date, find_category, load_categories
from fsm.core import RunContext
from pipelines.ingest.guards import assert_raw_content
from pipelines.ingest.models import IngestData, IngestError, IngestInput

logger = logging.getLogger(__name__)

_DEFAULT_CATEGORIES_CONFIG = Path(__file__).parents[4] / "config" / "categories.yaml"


@dataclass(slots=True)
class SplitControlBlocks:
    """S3: Remove category line from document body.

    Finds **Категория:** marker line and removes it from the markdown body
    to avoid polluting markdown parsing/chunking.
    """

    id: ClassVar[str] = "split_control_blocks"
    desc: ClassVar[str] = "Remove category line from body"

    categories_config: Path = field(default_factory=lambda: _DEFAULT_CATEGORIES_CONFIG)
    _allowed: list[str] = field(init=False)

    def __post_init__(self) -> None:
        self._allowed: list[str] = load_categories(self.categories_config)

    async def run(self, ctx: RunContext[IngestInput, IngestData]) -> None:
        ctx.data.desc = self.desc
        content = assert_raw_content(ctx.data, self.id)

        # Extract document date: content marker > YAML metadata > filename prefix
        extracted_date = extract_document_date(
            content, source_path=ctx.input.original_filename
        )

        if not extracted_date:
            logger.warning(
                "Document date not found: filename=%s source_path=%s",
                ctx.input.original_filename,
                ctx.input.source_path,
            )
            raise IngestError(
                "E_NO_DOCUMENT_DATE",
                f"Document date not found for {ctx.input.original_filename!r}",
            )
        ctx.data.document_date = extracted_date

        lines = content.split("\n")

        # Strip YAML metadata block from body if present (--- ... ---)
        if lines and lines[0].strip() == "---":
            for i in range(1, len(lines)):
                if lines[i].strip() == "---":
                    lines = lines[i + 1 :]
                    break

        # Remove category line if found (first occurrence in first 30 lines)
        match = find_category(lines, self._allowed, search_limit=30)
        if match:
            lines.pop(match.line_number)

        ctx.data.md_body = "\n".join(lines)
        ctx.data.desc = f"Cleaned: {len(lines)} lines, body_size={len(ctx.data.md_body)}, date={ctx.data.document_date}"
