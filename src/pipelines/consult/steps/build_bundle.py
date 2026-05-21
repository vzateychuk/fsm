"""C2: Build knowledge base context bundle."""

from typing import ClassVar

from src.fsm.core import RunContext
from src.pipelines.consult.bundle_builder import KBContextBundleBuilder
from src.pipelines.consult.config import ConsultConfig
from src.pipelines.consult.models import ConsultData, ConsultRequest


class BuildBundle:
    """C2: Assemble KB context bundle."""

    id: ClassVar[str] = "build_bundle"
    desc: ClassVar[str] = "C2: Build KB context bundle"

    def __init__(self, config: ConsultConfig) -> None:
        self.config = config
        self.builder = KBContextBundleBuilder(config)

    async def run(self, ctx: RunContext[ConsultRequest, ConsultData]) -> None:
        ctx.data.bundle = self.builder.build(
            query_chunks=ctx.data.query_chunks,
            recency_chunks=ctx.data.recency_chunks,
        )
