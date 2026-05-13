from dataclasses import dataclass

from fsm.core import RunContext, StepAction
from pipelines.number_pipeline.models import NumberInput, NumberData


@dataclass(slots=True)
class ParseNumbers(StepAction[NumberInput, NumberData]):
    """Парсинг чисел из строки"""

    id: str = "parse_numbers"

    async def run(self, ctx: RunContext[NumberInput, NumberData]) -> None:
        try:
            ctx.data.numbers = [
                int(x.strip())
                for x in ctx.input.raw_numbers.split(",")
                if x.strip()
            ]
        except ValueError:
            ctx.data.numbers = []


@dataclass(slots=True)
class CalculateSum(StepAction[NumberInput, NumberData]):
    """Расчет суммы чисел"""

    id: str = "calculate_sum"

    async def run(self, ctx: RunContext[NumberInput, NumberData]) -> None:
        ctx.data.sum_value = sum(ctx.data.numbers)


@dataclass(slots=True)
class FormatResult(StepAction[NumberInput, NumberData]):
    """Форматирование результата"""

    id: str = "format_result"

    async def run(self, ctx: RunContext[NumberInput, NumberData]) -> None:
        count = len(ctx.data.numbers)
        ctx.data.result = f"sum={ctx.data.sum_value}, count={count}, avg={ctx.data.sum_value / count if count > 0 else 0:.2f}"
