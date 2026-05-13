import logging
from typing import Any

from store.store import SavedProgress, Store

logger = logging.getLogger(__name__)


class InMemoryStore(Store):
    """In-memory реализация хранилища прогресса для тестирования"""

    def __init__(self) -> None:
        self._data: dict[str, SavedProgress] = {}

    async def load(self, run_id: str) -> SavedProgress | None:
        """Загрузить прогресс из памяти"""
        progress = self._data.get(run_id)
        if progress:
            logger.debug(f"Loaded progress from memory: run_id={run_id}")
        return progress

    async def save(self, progress: SavedProgress) -> None:
        """Сохранить прогресс в памяти"""
        self._data[progress["run_id"]] = progress
        logger.debug(f"Saved progress to memory: run_id={progress['run_id']}")
