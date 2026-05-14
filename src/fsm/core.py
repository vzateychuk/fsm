from typing import Generic, Protocol, TypeVar

from pydantic import BaseModel

TIn = TypeVar("TIn")
TData = TypeVar("TData", bound=BaseModel)


class RunContext(Generic[TIn, TData]):
    """Контекст выполнения саги"""

    def __init__(
        self,
        run_id: str,
        saga_name: str,
        cursor: int,
        input: TIn,
        data: TData,
    ) -> None:
        self.run_id = run_id
        self.saga_name = saga_name
        self.cursor = cursor
        self.input = input
        self.data = data


class SagaStep(Generic[TIn, TData], Protocol):
    """Interface/Протокол для шага саги

    Контракт:
    - id: str — уникальный идентификатор шага (обязателен, используется для логирования и отладки)
    - desc: str | None — опциональное описание шага
    - run() — асинхронный метод выполнения шага
    """

    id: str  # Обязателен - не может быть None или пустым

    desc: str | None = ""  # Опционально с дефолтом

    async def run(self, ctx: RunContext[TIn, TData]) -> None:
        """Выполнить шаг"""
        ...


class SagaDefinition(Generic[TIn, TData]):
    """Определение саги"""

    def __init__(self, name: str, steps: list[SagaStep[TIn, TData]]) -> None:
        self.name = name
        self.steps = steps
