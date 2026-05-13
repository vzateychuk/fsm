from fsm.models import SagaInput, SagaState


class NumberInput(SagaInput):
    """Входные данные для number pipeline"""

    raw_numbers: str


class NumberState(SagaState):
    """Состояние для number pipeline"""

    state_name: str = "number_state"
    numbers: list[int] = []
    sum_value: int | None = None
    result: str | None = None
