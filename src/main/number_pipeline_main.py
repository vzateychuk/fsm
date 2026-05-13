import asyncio
import logging
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from commons import setup_logging
from fsm.core import SagaDefinition
from fsm.saga_runner import SagaRunner
from pipelines.number_pipeline.models import NumberInput, NumberState
from pipelines.number_pipeline.steps import ParseNumbers, CalculateSum, FormatResult
from store.inmem.inmemory_store import InMemoryStore


async def main() -> None:
    """Number pipeline: обработка чисел (3 шага)"""

    setup_logging(log_file="logs/number_pipeline.log")
    logger = logging.getLogger(__name__)

    definition = SagaDefinition[NumberInput, NumberState](
        name="number_pipeline",
        steps=[ParseNumbers(), CalculateSum(), FormatResult()],
    )

    store = InMemoryStore()
    runner = SagaRunner(definition, store, NumberState)

    logger.info("===> Before run <===")

    await runner.run(
        run_id="number-run-001",
        input=NumberInput(raw_numbers="10, 20, 30, 40, 50"),
        initial_state=NumberState(),
    )

    logger.info("<=== After run ===>")


if __name__ == "__main__":
    asyncio.run(main())
