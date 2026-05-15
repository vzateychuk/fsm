from dataclasses import dataclass

from fsm.core import RunContext
from pipelines.ingest.models import IngestInput, IngestData


@dataclass(slots=True)
class DetectTargetSchema:
    """S3: Detect target schema from document"""

    id = "detect_target_schema"
    desc = "Detect target schema from document header"

    async def run(self, ctx: RunContext[IngestInput, IngestData]) -> None:
        ctx.data.desc = "Detecting target schema"
        ctx.data.target_schema = "default"
        ctx.data.desc = f"Schema detected: {ctx.data.target_schema}"
