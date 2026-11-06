"""Perfis de acesso: administrador da configuração, administradores e professores cadastrados."""

import hmac
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User
from app.security import (
    hash_password,
    issue_session,
    password_fingerprint,
    read_session,
    verify_password,
)
from app.settings import Settings

ROLES = ("admin", "professor")
BUILTIN_NAME = "Administrador do sistema"
# Hash descartável para que usuários inexistentes levem o mesmo tempo de verificação.
_DECOY_HASH = hash_password("movement-usuario-inexistente")


@dataclass(frozen=True)
class Principal:
    username: str
    full_name: str
    role: str
    user_id: UUID | None = None
    session_version: int = 0

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    @property
    def builtin(self) -> bool:
        return self.user_id is None


def builtin_principal(settings: Settings) -> Principal:
    return Principal(username=settings.operator_username, full_name=BUILTIN_NAME, role="admin")


def is_builtin_username(username: str, settings: Settings) -> bool:
    return hmac.compare_digest(username.encode(), settings.operator_username.encode())


def authenticate(session: Session, settings: Settings, username: str, password: str):
    if is_builtin_username(username, settings):
        password_hash = settings.operator_password_hash.get_secret_value()
        if not verify_password(password, password_hash):
            return None
        return builtin_principal(settings), password_hash
    user = session.scalar(select(User).where(User.username == username.strip().lower()))
    if user is None:
        verify_password(password, _DECOY_HASH)
        return None
    if not verify_password(password, user.password_hash) or not user.active:
        return None
    return principal_from_user(user), user.password_hash


def principal_from_user(user: User) -> Principal:
    return Principal(
        username=user.username,
        full_name=user.full_name,
        role=user.role,
        user_id=user.id,
        session_version=user.session_version,
    )


def issue_principal_session(settings: Settings, principal: Principal, password_hash: str) -> str:
    return issue_session(
        settings,
        username=principal.username,
        user_id=str(principal.user_id) if principal.user_id else None,
        password_hash=password_hash,
        session_version=principal.session_version,
    )


def resolve_session(session: Session, settings: Settings, token: str) -> Principal | None:
    payload = read_session(token, settings)
    if payload is None:
        return None
    if payload.get("uid") is None:
        expected = password_fingerprint(settings.operator_password_hash.get_secret_value())
        if is_builtin_username(payload["sub"], settings) and payload.get("pv") == expected:
            return builtin_principal(settings)
        return None
    try:
        user = session.get(User, UUID(str(payload["uid"])))
    except ValueError:
        return None
    if (
        user is None
        or not user.active
        or user.username != payload["sub"]
        or payload.get("pv") != password_fingerprint(user.password_hash)
        or payload.get("sv") != user.session_version
    ):
        return None
    return principal_from_user(user)
