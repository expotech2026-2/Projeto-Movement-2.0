from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.auth import Principal, resolve_session

bearer = HTTPBearer(auto_error=False)
Credentials = Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]


def database_session(request: Request) -> Iterator[Session]:
    with request.app.state.sessions() as session:
        yield session


Db = Annotated[Session, Depends(database_session)]


def require_user(request: Request, session: Db, credentials: Credentials) -> Principal:
    principal = (
        resolve_session(session, request.app.state.settings, credentials.credentials)
        if credentials
        else None
    )
    if principal is None:
        raise HTTPException(
            401, "Sessão inválida ou expirada", headers={"WWW-Authenticate": "Bearer"}
        )
    return principal


CurrentUser = Annotated[Principal, Depends(require_user)]


def require_admin(principal: CurrentUser) -> Principal:
    if not principal.is_admin:
        raise HTTPException(403, "Ação permitida apenas para administradores")
    return principal


AdminUser = Annotated[Principal, Depends(require_admin)]
