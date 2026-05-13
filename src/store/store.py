from typing import Optional, TypedDict, Protocol, Any


class SavedProgress(TypedDict):
    """Структура сохраненного прогресса"""

    run_id: str
    saga_name: str
    cursor: int
    state: dict[str, Any]


class Store(Protocol):
    """Протокол хранилища"""

    async def load(self, run_id: str) -> Optional[SavedProgress]:
        """Загрузить прогресс"""
        ...

    async def save(self, progress: SavedProgress) -> None:
        """Сохранить прогресс"""
        ...
