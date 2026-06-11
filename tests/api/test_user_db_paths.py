"""USER_DB_ROOT and resolve_user_db_path validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.api.user_db_paths import resolve_user_db_path


def test_resolve_user_db_path_default_is_absolute(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("USER_DB_ROOT", raising=False)

    path = resolve_user_db_path("alice")

    assert Path(path).is_absolute()
    assert path.endswith(f"{Path('alice.db').as_posix()}") or path.endswith("alice.db")


def test_resolve_user_db_path_honors_absolute_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "users"
    monkeypatch.setenv("USER_DB_ROOT", str(root))

    path = resolve_user_db_path("bob")

    assert path == str((root / "bob.db").resolve())


def test_resolve_user_db_path_resolves_relative_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("USER_DB_ROOT", "relative/db")

    path = resolve_user_db_path("carol")

    expected = (tmp_path / "relative" / "db" / "carol.db").resolve()
    assert path == str(expected)
    assert Path(path).is_absolute()


def test_resolve_user_db_path_rejects_empty_root(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("USER_DB_ROOT", "")

    with pytest.raises(ValueError, match="USER_DB_ROOT must not be empty"):
        resolve_user_db_path("alice")


def test_resolve_user_db_path_rejects_whitespace_root(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("USER_DB_ROOT", "   ")

    with pytest.raises(ValueError, match="USER_DB_ROOT must not be empty"):
        resolve_user_db_path("alice")


def test_resolve_user_db_path_rejects_path_separator_in_username(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("USER_DB_ROOT", "/data/db")

    with pytest.raises(ValueError, match="Invalid username for db path"):
        resolve_user_db_path("../etc/passwd")
