from dataclasses import dataclass

from fsm.core import RunContext, SagaStep
from pipelines.number_pipeline.models import NumberInput, NumberState


@dataclass(slots=True)
class ParseNumbers(SagaStep[NumberInput, NumberState]):
    """Шаг парсинга чисел из строки"""

    id: str = "parse_numbers"

    async def run(self, ctx: RunContext[NumberInput, NumberState]) -> None:
        try:
            ctx.state.numbers = [
                int(x.strip())
                for x in ctx.input.raw_numbers.split(",")
                if x.strip()
            ]
        except ValueError:
            ctx.state.numbers = []


@dataclass(slots=True)
class CalculateSum(SagaStep[NumberInput, NumberState]):
    """Шаг расчета суммы"""

    id: str = "calculate_sum"

    async def run(self, ctx: RunContext[NumberInput, NumberState]) -> None:
        ctx.state.sum_value = sum(ctx.state.numbers)


@dataclass(slots=True)
class FormatResult(SagaStep[NumberInput, NumberState]):
    """Шаг форматирования результата"""

    id: str = "format_result"

    async def run(self, ctx: RunContext[NumberInput, NumberState]) -> None:
        count = len(ctx.state.numbers)
        ctx.state.result = f"sum={ctx.state.sum_value}, count={count}, avg={ctx.state.sum_value / count if count > 0 else 0:.2f}"
