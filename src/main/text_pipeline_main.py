import asyncio
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from commons import setup_logging
from fsm.core import SagaDefinition
from fsm.saga import Saga
from pipelines.text_pipeline.models import TextInput, TextState
from pipelines.text_pipeline.steps import Preprocessing, Processing
from store.inmem.inmemory_store import InMemoryStore


async def main() -> None:
    """Text pipeline: обработка текста (2 шага)"""

    setup_logging(log_file="logs/text_pipeline.log")

    print("=" * 60)
    print("TEXT PIPELINE: Tokenization and Counting")
    print("=" * 60)

    definition = SagaDefinition[TextInput, TextState](
        name="text_pipeline",
        steps=[Preprocessing(), Processing()],
    )

    store = InMemoryStore()
    saga = Saga(definition, store, TextState)

    ctx = await saga.run(
        run_id="text-run-001",
        input=TextInput(raw_text="  hello beautiful world  "),
        initial_state=TextState(),
    )

    print("\n" + "=" * 60)
    print(f"RESULT: {ctx.state.result}")
    print(f"TOKENS: {ctx.state.tokens}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
