"""Per-user DB isolation (Phase 6)."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.api.factory import create_shared_context
from src.common.patient import PatientInfo

PROJECT_ROOT = Path(__file__).resolve().parents[2]


SAMPLE_MD = """**Категория:** Анализы

# Test

Sample content for isolation test.
"""


@pytest.mark.asyncio
async def test_documents_isolated_between_user_dbs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(PROJECT_ROOT)
    monkeypatch.setenv("SYSTEM_DB_PATH", str(tmp_path / "system.db"))
    shared = await create_shared_context()

    alice_db = str(tmp_path / "alice.db")
    bob_db = str(tmp_path / "bob.db")

    alice = await shared.user_factory.get("alice", alice_db)
    bob = await shared.user_factory.get("bob", bob_db)

    await alice.profile_service.update_profile(
        PatientInfo(name="Alice", age=30, sex="F", date_of_birth="1994-01-01")
    )

    await alice.ingest_service.ingest_document(SAMPLE_MD, original_filename="2024-01-15_test.md")

    alice_docs = await alice.documents_service.list_documents()
    bob_docs = await bob.documents_service.list_documents()

    assert len(alice_docs) == 1
    assert len(bob_docs) == 0


@pytest.mark.asyncio
async def test_sessions_isolated_between_user_dbs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(PROJECT_ROOT)
    monkeypatch.setenv("SYSTEM_DB_PATH", str(tmp_path / "system.db"))
    shared = await create_shared_context()

    alice = await shared.user_factory.get("alice", str(tmp_path / "alice.db"))
    bob = await shared.user_factory.get("bob", str(tmp_path / "bob.db"))

    created = await alice.sessions_service.create_session(title="Alice session")
    alice_sessions = await alice.sessions_service.list_sessions()
    bob_sessions = await bob.sessions_service.list_sessions()

    assert len(alice_sessions) == 1
    assert alice_sessions[0].session_id == created.session_id
    assert len(bob_sessions) == 0
