from dataclasses import dataclass
from pydantic import BaseModel

from fsm.core import RunContext, SagaStep


class SagaInput(BaseModel):
    """Входные данные для саги"""

    raw_text: str


class SagaState(BaseModel):
    """Состояние саги"""

    text: str | None = None
    tokens: list[str] = []
    result: str | None = None


@dataclass(slots=True)
class Preprocessing(SagaStep[SagaInput, SagaState]):
    """Шаг предобработки"""

    id: str = "preprocessing"

    async def run(self, ctx: RunContext[SagaInput, SagaState]) -> None:
        ctx.state.text = ctx.input.raw_text.strip()
        ctx.state.tokens = ctx.state.text.split()


@dataclass(slots=True)
class Processing(SagaStep[SagaInput, SagaState]):
    """Шаг обработки"""

    id: str = "processing"

    async def run(self, ctx: RunContext[SagaInput, SagaState]) -> None:
        ctx.state.result = f"tokens={len(ctx.state.tokens)}"
