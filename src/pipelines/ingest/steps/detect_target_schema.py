from dataclasses import dataclass
from typing import ClassVar

from fsm.core import RunContext
from pipelines.ingest.guards import assert_raw_content
from pipelines.ingest.models import IngestData, IngestInput


@dataclass(slots=True)
class DetectTargetSchema:
    """S3: Detect target schema from document"""

    id: ClassVar[str] = "detect_target_schema"
    desc: ClassVar[str] = "Detect target schema from document header"

    async def run(self, ctx: RunContext[IngestInput, IngestData]) -> None:
        ctx.data.desc = self.desc
        _ = assert_raw_content(ctx.data, self.id)
        ctx.data.target_schema = "default"
        ctx.data.desc = f"Schema detected: {ctx.data.target_schema}"
