import secrets
import time

from app.auth import builtin_principal, issue_principal_session, resolve_session
from app.security import hash_password, issue_session, read_session, verify_password
from app.settings import Settings


def settings_for_tests(**changes) -> Settings:
    return Settings(
        database_url="postgresql+psycopg://test@localhost/movement_test",
        session_secret=secrets.token_urlsafe(32),
        operator_password_hash=hash_password("operator-password"),
        session_ttl_seconds=60,
        **changes,
    )


def test_password_hash_is_salted_and_checks_password():
    first = hash_password("operator-password")
    second = hash_password("operator-password")
    assert first != second
    assert verify_password("operator-password", first)
    assert not verify_password("wrong", first)
    assert not verify_password("operator-password", "malformed")


def test_session_expires_and_cannot_be_reused_with_another_secret(monkeypatch):
    settings = settings_for_tests()
    issued_at = time.time()
    token = issue_session(settings, username="admin", user_id=None, password_hash="hash")
    assert read_session(token, settings)["sub"] == "admin"
    other_secret = settings.model_copy(
        update={"session_secret": settings.session_secret.__class__(secrets.token_urlsafe(32))}
    )
    assert read_session(token, other_secret) is None
    assert read_session("not-a-token", settings) is None
    monkeypatch.setattr("itsdangerous.timed.time.time", lambda: issued_at + 120)
    assert read_session(token, settings) is None


def test_builtin_admin_session_follows_configured_username_and_password():
    settings = settings_for_tests()
    password_hash = settings.operator_password_hash.get_secret_value()
    token = issue_principal_session(settings, builtin_principal(settings), password_hash)
    principal = resolve_session(None, settings, token)
    assert principal.is_admin and principal.builtin
    renamed = settings.model_copy(update={"operator_username": "other"})
    assert resolve_session(None, renamed, token) is None
    new_password = settings.model_copy(
        update={
            "operator_password_hash": settings.operator_password_hash.__class__(
                hash_password("another-password")
            )
        }
    )
    assert resolve_session(None, new_password, token) is None
