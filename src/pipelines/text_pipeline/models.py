from fsm.models import SagaInput, SagaData


class TextInput(SagaInput):
    """Входные данные для text pipeline"""

    raw_text: str


class TextData(SagaData):
    """Данные для text pipeline"""

    text: str | None = None
    tokens: list[str] = []
    result: str | None = None
