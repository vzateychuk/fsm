import json
from dataclasses import dataclass

import aiosqlite

from store.store import SavedProgress, Store


@dataclass(slots=True)
class SqlStore:
    db_path: str

    async def load(self, run_id: str) -> SavedProgress | None:
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            async with conn.execute(
                "SELECT run_id, saga_name, cursor, state, source_path FROM saga_progress WHERE run_id = ?",
                (run_id,),
            ) as cursor:
                row = await cursor.fetchone()

        if row is None:
            return None
        progress = SavedProgress(
            run_id=row["run_id"],
            saga_name=row["saga_name"],
            cursor=row["cursor"],
            state=json.loads(row["state"]),
        )
        if row["source_path"]:
            progress["source_path"] = row["source_path"]
        return progress

    async def save(self, progress: SavedProgress) -> None:
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute(
                "INSERT OR REPLACE INTO saga_progress (run_id, saga_name, cursor, state, source_path)"
                " VALUES (?, ?, ?, ?, ?)",
                (
                    progress["run_id"],
                    progress["saga_name"],
                    progress["cursor"],
                    json.dumps(progress["state"]),
                    progress.get("source_path"),
                ),
            )
            await conn.commit()

