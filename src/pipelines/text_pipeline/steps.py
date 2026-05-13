from dataclasses import dataclass

from fsm.core import RunContext, StepAction
from pipelines.text_pipeline.models import TextInput, TextData


@dataclass(slots=True)
class Preprocessing(StepAction[TextInput, TextData]):
    """Предобработка текста: очистка и токенизация"""

    id: str = "preprocessing"

    async def run(self, ctx: RunContext[TextInput, TextData]) -> None:
        ctx.data.text = ctx.input.raw_text.strip()
        ctx.data.tokens = ctx.data.text.split()


@dataclass(slots=True)
class Processing(StepAction[TextInput, TextData]):
    """Обработка: подсчет токенов"""

    id: str = "processing"

    async def run(self, ctx: RunContext[TextInput, TextData]) -> None:
        ctx.data.result = f"tokens={len(ctx.data.tokens)}"
