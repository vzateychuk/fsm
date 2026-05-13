from typing import Generic, Protocol, TypeVar, Any
from dataclasses import dataclass

TIn = TypeVar("TIn")
TData = TypeVar("TData")


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
    """Interface/Протокол для шага саги"""

    id: str

    async def run(self, ctx: RunContext[TIn, TData]) -> None:
        """Выполнить шаг"""
        ...


@dataclass(slots=True)
class StepAction(Generic[TIn, TData], SagaStep[TIn, TData]):
    """Абстрактный базовый класс для step action-ов (шаги pipeline), implements SagaStep"""

    async def run(self, ctx: RunContext[TIn, TData]) -> None:
        """Выполнить действие"""
        raise NotImplementedError


class SagaDefinition(Generic[TIn, TData]):
    """Определение саги"""

    def __init__(self, name: str, steps: list[SagaStep[TIn, TData]]) -> None:
        self.name = name
        self.steps = steps


class SagaProgressStore(Protocol):
    """Протокол хранилища прогресса"""

    async def load(self, run_id: str) -> dict[str, Any] | None:
        """Загрузить сохраненный прогресс"""
        ...

    async def save(self, data: dict[str, Any]) -> None:
        """Сохранить прогресс"""
        ...
