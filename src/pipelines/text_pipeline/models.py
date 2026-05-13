from fsm.models import SagaInput, SagaState


class TextInput(SagaInput):
    """Входные данные для text pipeline"""

    raw_text: str


class TextState(SagaState):
    """Состояние для text pipeline"""

    state_name: str = "text_state"
    text: str | None = None
    tokens: list[str] = []
    result: str | None = None
