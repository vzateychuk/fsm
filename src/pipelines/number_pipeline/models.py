from pydantic import BaseModel


class NumberInput(BaseModel):
    """Входные данные для number pipeline"""

    raw_numbers: str


class NumberState(BaseModel):
    """Состояние number pipeline"""

    numbers: list[int] = []
    sum_value: int | None = None
    result: str | None = None
