from pydantic import BaseModel


class SagaInput(BaseModel):
    """Базовый класс для входных данных saga"""

    pass


class SagaData(BaseModel):
    """Базовый класс для данных контекста"""

    pass
