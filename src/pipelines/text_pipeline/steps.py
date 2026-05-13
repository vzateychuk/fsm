from dataclasses import dataclass

from fsm.core import RunContext, StepAction
from pipelines.text_pipeline.models import TextInput, TextState


@dataclass(slots=True)
class Preprocessing(StepAction[TextInput, TextState]):
    """Предобработка текста: очистка и токенизация"""

    id: str = "preprocessing"

    async def run(self, ctx: RunContext[TextInput, TextState]) -> None:
        ctx.state.text = ctx.input.raw_text.strip()
        ctx.state.tokens = ctx.state.text.split()


@dataclass(slots=True)
class Processing(StepAction[TextInput, TextState]):
    """Обработка: подсчет токенов"""

    id: str = "processing"

    async def run(self, ctx: RunContext[TextInput, TextState]) -> None:
        ctx.state.result = f"tokens={len(ctx.state.tokens)}"
