from typing import Generic, Protocol, TypeVar, Any
from dataclasses import dataclass

TIn = TypeVar("TIn")
TState = TypeVar("TState")


class RunContext(Generic[TIn, TState]):
    """Контекст выполнения саги"""

    def __init__(
        self,
        run_id: str,
        saga_name: str,
        cursor: int,
        input: TIn,
        state: TState,
    ) -> None:
        self.run_id = run_id
        self.saga_name = saga_name
        self.cursor = cursor
        self.input = input
        self.state = state


class SagaStep(Generic[TIn, TState], Protocol):
    """Interface/Протокол для шага саги"""

    id: str

    async def run(self, ctx: RunContext[TIn, TState]) -> None:
        """Выполнить шаг"""
        ...


@dataclass(slots=True)
class StepAction(Generic[TIn, TState], SagaStep[TIn, TState]):
    """Абстрактный базовый класс для step action-ов (шаги pipeline), implements SagaStep"""

    async def run(self, ctx: RunContext[TIn, TState]) -> None:
        """Выполнить действие"""
        raise NotImplementedError


class SagaDefinition(Generic[TIn, TState]):
    """Определение саги"""

    def __init__(self, name: str, steps: list[SagaStep[TIn, TState]]) -> None:
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
