import asyncio
import logging
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from fsm.core import SagaDefinition
from saga.models import SagaInput, SagaState, Preprocessing, Processing
from saga.saga import Saga
from store.inmem.inmemory_store import InMemoryStore


def setup_logging(level: int = logging.INFO, log_file: str | None = None) -> None:
    """Настроить логирование в консоль и опционально в файл"""

    # Формат логов
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    # Консоль
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(logging.Formatter(log_format))

    # Файл (опционально)
    handlers = [console_handler]
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(level)
        file_handler.setFormatter(logging.Formatter(log_format))
        handlers.append(file_handler)

    # Настроить root logger
    logging.basicConfig(level=level, handlers=handlers)


async def main() -> None:
    """Example: run a saga with 2 steps"""

    # Настроить логирование (INFO в консоль, DEBUG в файл)
    setup_logging(level=logging.INFO, log_file="saga.log")

    # Для DEBUG логов в консоль раскомментируй эту строку:
    # setup_logging(level=logging.DEBUG, log_file="saga.log")

    # Define saga steps
    definition = SagaDefinition[SagaInput, SagaState](
        name="text_pipeline",
        steps=[Preprocessing(), Processing()],
    )

    # Create store and saga
    store = InMemoryStore()
    saga = Saga(definition, store, SagaState)

    # Run saga
    ctx = await saga.run(
        run_id="run-123",
        input=SagaInput(raw_text="  hello world "),
        initial_state=SagaState(),
        resume=True,
    )

    print(f"\nResult: {ctx.state.result}")  # "Result: tokens=2"


if __name__ == "__main__":
    asyncio.run(main())
