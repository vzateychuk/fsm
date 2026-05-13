from typing import Generic, TypeVar

from fsm.core import SagaDefinition, SagaProgressStore
from saga.saga import Saga

TIn = TypeVar("TIn")
TState = TypeVar("TState")


class SagaFactory:
    """Фабрика для создания саг"""

    def __init__(self, store: SagaProgressStore) -> None:
        self._store = store

    def create(
        self,
        saga_def: SagaDefinition[TIn, TState],
        *,
        state_type: type[TState],
    ) -> Saga[TIn, TState]:
        return Saga(saga_def, self._store, state_type)
