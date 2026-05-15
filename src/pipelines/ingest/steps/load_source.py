import asyncio
from dataclasses import dataclass
from pathlib import Path

from fsm.core import RunContext
from pipelines.ingest.models import IngestInput, IngestData


@dataclass(slots=True)
class LoadSource:
    """S1: Load markdown file from source path"""

    id = "load_source"
    desc = "Load markdown file from source"

    async def run(self, ctx: RunContext[IngestInput, IngestData]) -> None:
        ctx.data.desc = self.desc
        try:
            text = await asyncio.to_thread(Path(ctx.input.source_path).read_text, encoding="utf-8")
            ctx.data.raw_content = text
            ctx.data.desc = f"Loaded {len(ctx.data.raw_content)} characters"
        except Exception as e:
            ctx.data.desc = f"Error loading file: {e}"
            raise
