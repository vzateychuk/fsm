"""AuthService.register rollback preserves the original error."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.auth import AuthService


@pytest.mark.asyncio
async def test_register_reraises_original_error_when_unlink_fails(tmp_path: Path) -> None:
    db_path = str(tmp_path / "alice.db")
    system = AsyncMock()
    system.username_exists.return_value = False

    user_factory = AsyncMock()
    user_factory.get.side_effect = RuntimeError("profile init failed")

    auth = AuthService(system, user_factory)

    db_file = tmp_path / "alice.db"
    db_file.write_text("partial", encoding="utf-8")

    with (
        patch("src.services.auth.resolve_user_db_path", return_value=db_path),
        patch("src.services.auth.ensure_schema", new_callable=AsyncMock),
        patch.object(Path, "unlink", side_effect=OSError("permission denied")),
    ):
        with pytest.raises(RuntimeError, match="profile init failed"):
            await auth.register("alice", "password123")

    system.delete_account.assert_awaited_once_with("alice")
