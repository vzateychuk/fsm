from __future__ import annotations

from typing import Any, Generic, Protocol, Sequence, TypeVar
from pydantic import BaseModel, ConfigDict, Field

TIn = TypeVar("TIn")
TState = TypeVar("TState", bound=BaseModel)

class RunContext(BaseModel, Generic[TIn, TState]):
    """
    Контекст исполнения. Он мутируемый: шаги изменяют ctx.state.
    Храним отдельно input (необязательно) и state (то, что сохраняем для resume).
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)

    run_id: str
    saga_name: str
    cursor: int = 0  # индекс следующего шага

    input: TIn
    state: TState

    # можно хранить технические штуки, не сохраняемые в БД:
    # logger: Any | None = None  # но pydantic будет пытаться сериализовать; лучше держать отдельно


class SagaStep(Protocol[TIn, TState]):
    id: str
    async def run(self, ctx: RunContext[TIn, TState]) -> None: ...


class SagaDefinition(Generic[TIn, TState]):
    def __init__(self, name: str, steps: Sequence[SagaStep[TIn, TState]]) -> None:
        self.name = name
        self.steps = list(steps)