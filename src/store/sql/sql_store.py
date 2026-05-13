from store.store import SavedProgress, Store


class SQLStore(Store):
    """SQL-хранилище для сохранения прогресса саг"""

    async def load(self, run_id: str) -> SavedProgress | None:
        """SELECT run_id, saga_name, cursor, state_json FROM saga_progress WHERE run_id=:run_id"""
        # TODO: реализовать подключение к БД
        return None

    async def save(self, progress: SavedProgress) -> None:
        """UPSERT по run_id"""
        # TODO: реализовать сохранение в БД
        pass
