from typing import Any, NotRequired, Protocol, TypedDict


class SavedProgress(TypedDict):
    """Структура сохраненного прогресса"""

    run_id: str
    saga_name: str
    cursor: int
    state: dict[str, Any]
    source_path: NotRequired[str]


class Store(Protocol):
    """Протокол хранилища"""

    async def load(self, run_id: str) -> SavedProgress | None:
        """Загрузить прогресс"""
        ...

    async def save(self, progress: SavedProgress) -> None:
        """Сохранить прогресс"""
        ...
