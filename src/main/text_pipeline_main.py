import asyncio
import logging
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from commons import setup_logging
from fsm.core import SagaDefinition
from fsm.saga_runner import SagaRunner
from pipelines.text_pipeline.models import TextInput, TextData
from pipelines.text_pipeline.steps import Preprocessing, Processing
from store.inmem.inmemory_store import InMemoryStore


async def main() -> None:
    """Text pipeline: обработка текста (2 шага)"""

    setup_logging(log_file="logs/text_pipeline.log")
    logger = logging.getLogger(__name__)

    definition = SagaDefinition[TextInput, TextData](
        name="text_pipeline",
        steps=[Preprocessing(), Processing()],
    )

    store = InMemoryStore()
    runner = SagaRunner(definition, store, TextData)

    logger.info("===> Before run <===")

    await runner.run(
        run_id="text-run-001",
        input=TextInput(raw_text="  hello beautiful world  "),
        initial_state=TextData(),
    )

    logger.info("<=== After run ===>")

if __name__ == "__main__":
    asyncio.run(main())
