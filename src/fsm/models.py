from pydantic import BaseModel


class SagaInput(BaseModel):
    """Базовый класс для входных данных saga"""

    pass


class SagaState(BaseModel):
    """Базовый класс для состояния saga"""

    state_name: str = "state"
