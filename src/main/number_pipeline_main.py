import asyncio
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from commons import setup_logging
from fsm.core import SagaDefinition
from fsm.saga import Saga
from pipelines.number_pipeline.models import NumberInput, NumberState
from pipelines.number_pipeline.steps import ParseNumbers, CalculateSum, FormatResult
from store.inmem.inmemory_store import InMemoryStore


async def main() -> None:
    """Number pipeline: обработка чисел (3 шага)"""

    setup_logging(log_file="logs/number_pipeline.log")

    print("=" * 60)
    print("NUMBER PIPELINE: Parse, Sum, Format (3 steps)")
    print("=" * 60)

    definition = SagaDefinition[NumberInput, NumberState](
        name="number_pipeline",
        steps=[ParseNumbers(), CalculateSum(), FormatResult()],
    )

    store = InMemoryStore()
    saga = Saga(definition, store, NumberState)

    ctx = await saga.run(
        run_id="number-run-001",
        input=NumberInput(raw_numbers="10, 20, 30, 40, 50"),
        initial_state=NumberState(),
        resume=True,
    )

    print("\n" + "=" * 60)
    print(f"RESULT: {ctx.state.result}")
    print(f"NUMBERS: {ctx.state.numbers}")
    print(f"SUM: {ctx.state.sum_value}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
