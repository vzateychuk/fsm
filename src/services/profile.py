"""ProfileService — patient profile in per-user SQLite."""
from __future__ import annotations

from src.common.patient import PatientInfo
from src.store.sql.sqlite_internal_store import SqliteInternalStore


class ProfileService:
    """Application service for user profile read/write."""

    def __init__(self, internal_store: SqliteInternalStore) -> None:
        self._store = internal_store

    async def get_profile(self) -> PatientInfo:
        profile = await self._store.get_user_profile()
        if profile is None:
            return PatientInfo(
                name="",
                age=0,
                sex="",
                date_of_birth="",
            )
        return profile

    async def update_profile(self, profile: PatientInfo) -> PatientInfo:
        await self._store.upsert_user_profile(profile)
        return profile

    @staticmethod
    def is_complete(profile: PatientInfo) -> bool:
        return bool(
            profile.name.strip()
            and profile.age > 0
            and profile.sex.strip()
            and profile.date_of_birth.strip()
        )
