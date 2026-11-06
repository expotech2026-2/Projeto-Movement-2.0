from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import is_builtin_username
from app.dependencies import AdminUser, Db, require_admin
from app.models import User
from app.security import hash_password

Role = Literal["admin", "professor"]


class UserUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    full_name: str = Field(min_length=1, max_length=120)
    role: Role
    active: bool = Field(default=True, strict=True)
    password: str | None = Field(default=None, min_length=12, max_length=256)


class UserCreate(UserUpdate):
    username: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]{2,59}$")
    password: str = Field(min_length=12, max_length=256)

    @field_validator("username", mode="before")
    @classmethod
    def normalize_username(cls, value):
        return value.strip().lower() if isinstance(value, str) else value


class UserOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    username: str
    full_name: str
    role: Role
    active: bool
    created_at: datetime


def create_users_router() -> APIRouter:
    router = APIRouter(prefix="/users", dependencies=[Depends(require_admin)], tags=["Usuários"])

    def get_user_for_update(session: Session, user_id: UUID) -> User:
        user = session.get(User, user_id, with_for_update=True, populate_existing=True)
        if user is None:
            raise HTTPException(404, "Usuário não encontrado")
        return user

    @router.get("", response_model=list[UserOutput])
    def users(session: Db):
        return session.scalars(select(User).order_by(User.full_name, User.username)).all()

    @router.post("", response_model=UserOutput, status_code=201)
    def create_user(payload: UserCreate, request: Request, session: Db):
        if is_builtin_username(payload.username, request.app.state.settings):
            raise HTTPException(409, "Este usuário é reservado ao administrador do sistema")
        user = User(
            username=payload.username,
            full_name=payload.full_name,
            role=payload.role,
            active=payload.active,
            password_hash=hash_password(payload.password),
        )
        session.add(user)
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            raise HTTPException(409, "Já existe um usuário com este login") from None
        return user

    @router.put("/{user_id}", response_model=UserOutput)
    def update_user(user_id: UUID, payload: UserUpdate, session: Db, principal: AdminUser):
        user = get_user_for_update(session, user_id)
        if principal.user_id == user.id and (payload.role != "admin" or not payload.active):
            raise HTTPException(409, "Você não pode remover o próprio acesso de administrador")
        if user.active != payload.active or user.role != payload.role:
            user.session_version += 1
        user.full_name = payload.full_name
        user.role = payload.role
        user.active = payload.active
        if payload.password:
            user.password_hash = hash_password(payload.password)
        session.commit()
        return user

    @router.delete("/{user_id}", status_code=204)
    def delete_user(user_id: UUID, session: Db, principal: AdminUser):
        user = get_user_for_update(session, user_id)
        if principal.user_id == user.id:
            raise HTTPException(409, "Você não pode excluir a própria conta")
        session.delete(user)
        session.commit()
        return Response(status_code=204)

    return router
