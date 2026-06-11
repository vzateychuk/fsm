"""AppError subclasses — stable codes and HTTP statuses."""

from __future__ import annotations

from src.services.errors import (
    AppError,
    InvalidCredentialsError,
    ProfileIncompleteError,
    UnauthorizedError,
    UsernameReservedError,
    UsernameTakenError,
)


def test_profile_incomplete_error_is_app_error_with_403() -> None:
    err = ProfileIncompleteError("Complete your profile before using this feature.")
    assert isinstance(err, AppError)
    assert err.code == "profile_incomplete"
    assert err.http_status == 403
    assert err.message == "Complete your profile before using this feature."


def test_auth_related_error_codes() -> None:
    assert UnauthorizedError("x").code == "unauthorized"
    assert UnauthorizedError("x").http_status == 401
    assert InvalidCredentialsError("x").code == "invalid_credentials"
    assert InvalidCredentialsError("x").http_status == 401
    assert UsernameTakenError("x").code == "username_taken"
    assert UsernameTakenError("x").http_status == 409
    assert UsernameReservedError("x").code == "username_reserved"
    assert UsernameReservedError("x").http_status == 409
