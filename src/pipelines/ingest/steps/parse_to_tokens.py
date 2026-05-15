from dataclasses import dataclass
from typing import ClassVar

from fsm.core import RunContext
from pipelines.ingest.guards import assert_md_body
from pipelines.ingest.models import IngestInput, IngestData


@dataclass(slots=True)
class ParseToTokens:
    """S5: Parse markdown body to tokens"""

    id: ClassVar[str] = "parse_to_tokens"
    desc: ClassVar[str] = "Parse markdown to tokens for stable chunking"

    async def run(self, ctx: RunContext[IngestInput, IngestData]) -> None:
        ctx.data.desc = self.desc
        # Simple parser: each non-empty line is a token
        md_body = assert_md_body(ctx.data, self.id)
        tokens = []
        for line in md_body.split("\n"):
            line = line.strip()
            if line:
                token_type = "heading" if line.startswith("#") else "paragraph"
                tokens.append({
                    "type": token_type,
                    "content": line,
                    "level": len(line) - len(line.lstrip("#")) if token_type == "heading" else 0
                })
        ctx.data.tokens = tokens
        ctx.data.desc = f"Parsed {len(tokens)} tokens"
