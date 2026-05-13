from fsm.models import SagaInput, SagaData


class NumberInput(SagaInput):
    """Входные данные для number pipeline"""

    raw_numbers: str


class NumberData(SagaData):
    """Данные для number pipeline"""

    numbers: list[int] = []
    sum_value: int | None = None
    result: str | None = None
