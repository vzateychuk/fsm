from dataclasses import dataclass

from fsm.core import RunContext, SagaStep
from pipelines.text_pipeline.models import SagaInput, SagaState


@dataclass(slots=True)
class Preprocessing(SagaStep[SagaInput, SagaState]):
    """Шаг предобработки текста"""

    id: str = "preprocessing"

    async def run(self, ctx: RunContext[SagaInput, SagaState]) -> None:
        ctx.state.text = ctx.input.raw_text.strip()
        ctx.state.tokens = ctx.state.text.split()


@dataclass(slots=True)
class Processing(SagaStep[SagaInput, SagaState]):
    """Шаг обработки токенов"""

    id: str = "processing"

    async def run(self, ctx: RunContext[SagaInput, SagaState]) -> None:
        ctx.state.result = f"tokens={len(ctx.state.tokens)}"
