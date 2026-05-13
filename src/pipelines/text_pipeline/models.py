from pydantic import BaseModel


class SagaInput(BaseModel):
    """Входные данные для text pipeline"""

    raw_text: str


class SagaState(BaseModel):
    """Состояние text pipeline"""

    text: str | None = None
    tokens: list[str] = []
    result: str | None = None
