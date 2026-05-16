from dataclasses import dataclass
from typing import ClassVar

from fsm.core import RunContext
from pipelines.ingest.guards import assert_md_body
from pipelines.ingest.models import IngestData, IngestError, IngestInput
from pipelines.ingest.parsers.markdown_it import parse_markdown_to_tokens


@dataclass(slots=True)
class ParseToTokens:
    """S5: Parse markdown body to structured tokens using markdown-it-py.

    Recognizes block-level elements: heading, paragraph, table, list, fence (code).
    Extracts plain-text content with inline markup removed.
    """

    id: ClassVar[str] = "parse_to_tokens"
    desc: ClassVar[str] = "Parse markdown to tokens for stable chunking"

    async def run(self, ctx: RunContext[IngestInput, IngestData]) -> None:
        ctx.data.desc = self.desc
        md_body = assert_md_body(ctx.data, self.id)

        try:
            tokens = parse_markdown_to_tokens(md_body)
            ctx.data.tokens = tokens
            ctx.data.desc = f"Parsed {len(tokens)} tokens"
        except Exception as e:
            raise IngestError("E_MD_PARSE_FAIL", f"Markdown parsing failed: {e}") from e
