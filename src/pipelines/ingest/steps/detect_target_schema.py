from dataclasses import dataclass
from typing import ClassVar

from common.utils.parsers import find_schema_id
from fsm.core import RunContext
from pipelines.ingest.guards import assert_raw_content
from pipelines.ingest.models import IngestData, IngestError, IngestInput


@dataclass(slots=True)
class DetectTargetSchema:
    """S3: Detect target schema from document"""

    id: ClassVar[str] = "detect_target_schema"
    desc: ClassVar[str] = "Detect target schema from document header"

    async def run(self, ctx: RunContext[IngestInput, IngestData]) -> None:
        ctx.data.desc = self.desc
        content = assert_raw_content(ctx.data, self.id)
        lines = content.split("\n")

        match = find_schema_id(lines, search_limit=30)
        if not match:
            raise IngestError("E_NO_SCHEMA_ID", "Target Schema ID not found in document")

        ctx.data.target_schema = match.schema_id
        ctx.data.desc = f"Schema detected: {match.schema_id}"
