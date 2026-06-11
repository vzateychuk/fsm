"""Username validation for registration."""

from __future__ import annotations

import re

USERNAME_PATTERN = re.compile(r"^[a-z][a-z0-9_-]{2,31}$")
RESERVED_USERNAMES = frozenset({"system", "default", "admin"})


def validate_username(username: str) -> str | None:
    """Return error message if invalid, else None."""
    if not USERNAME_PATTERN.match(username):
        return (
            "Username must be 3–32 characters, start with a letter, "
            "and contain only lowercase letters, digits, hyphens, and underscores."
        )
    if username in RESERVED_USERNAMES:
        return f"Username {username!r} is reserved."
    return None
