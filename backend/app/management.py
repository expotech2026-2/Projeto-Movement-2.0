import secrets
from datetime import date
from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import AirConditioner, Device, Room
from app.retention import monthly_history
from app.security import hash_device_token


class RoomInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=120)
    location: str = Field(default="", max_length=120)
    capacity: int = Field(default=1, ge=1, le=10000, strict=True)


class RoomOutput(RoomInput):
    model_config = ConfigDict(from_attributes=True)
    id: str


class ApplianceInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=120)
    kind: Literal["split", "janela", "cassete", "piso_teto", "portatil", "vrf"]
    brand: str = Field(default="", max_length=80)
    model: str = Field(default="", max_length=80)
    capacity_btu: int = Field(ge=1000, le=500000, strict=True)
    inverter: bool = Field(default=False, strict=True)
    status: Literal["ativo", "manutencao", "inativo"] = "ativo"


class ApplianceOutput(ApplianceInput):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    room_id: str


class DeviceOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    room_id: str
    enabled: bool


class DeviceCredential(DeviceOutput):
    token: str


class MonthlyOutput(BaseModel):
    month: date
    sample_count: int
    avg_temp_inside: float
    avg_temp_outside: float
    avg_humidity_inside: float
    avg_humidity_outside: float
    avg_occupancy: float
    ac_on_percent: float
    finalized: bool


def commit(session: Session):
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(409, "Registro vinculado a outros dados ou já cadastrado") from None


def get_room(session: Session, room_id: str) -> Room:
    room = session.get(Room, room_id)
    if room is None:
        raise HTTPException(404, "Sala não encontrada")
    return room


def create_management_router(database_dependency, operator_dependency) -> APIRouter:
    router = APIRouter(dependencies=[Depends(operator_dependency)], tags=["Gestão de salas"])
    Db = Annotated[Session, Depends(database_dependency)]

    @router.get("/rooms", response_model=list[RoomOutput])
    def rooms(session: Db):
        return session.scalars(select(Room).order_by(Room.name, Room.id)).all()

    @router.post("/rooms", response_model=RoomOutput, status_code=201)
    def create_room(payload: RoomInput, session: Db):
        room = Room(id=f"sala-{uuid4().hex[:16]}", **payload.model_dump())
        session.add(room)
        commit(session)
        return room

    @router.put("/rooms/{room_id}", response_model=RoomOutput)
    def update_room(room_id: str, payload: RoomInput, session: Db):
        room = get_room(session, room_id)
        for field, value in payload.model_dump().items():
            setattr(room, field, value)
        commit(session)
        return room

    @router.delete("/rooms/{room_id}", status_code=204)
    def delete_room(room_id: str, session: Db):
        session.delete(get_room(session, room_id))
        commit(session)
        return Response(status_code=204)

    @router.get("/rooms/{room_id}/appliances", response_model=list[ApplianceOutput])
    def appliances(room_id: str, session: Db):
        get_room(session, room_id)
        return session.scalars(
            select(AirConditioner)
            .where(AirConditioner.room_id == room_id)
            .order_by(AirConditioner.name)
        ).all()

    @router.post("/rooms/{room_id}/appliances", response_model=ApplianceOutput, status_code=201)
    def create_appliance(room_id: str, payload: ApplianceInput, session: Db):
        get_room(session, room_id)
        appliance = AirConditioner(room_id=room_id, **payload.model_dump())
        session.add(appliance)
        commit(session)
        return appliance

    def get_appliance(session: Session, room_id: str, appliance_id: UUID):
        appliance = session.get(AirConditioner, appliance_id)
        if appliance is None or appliance.room_id != room_id:
            raise HTTPException(404, "Aparelho não encontrado nesta sala")
        return appliance

    @router.put("/rooms/{room_id}/appliances/{appliance_id}", response_model=ApplianceOutput)
    def update_appliance(room_id: str, appliance_id: UUID, payload: ApplianceInput, session: Db):
        appliance = get_appliance(session, room_id, appliance_id)
        for field, value in payload.model_dump().items():
            setattr(appliance, field, value)
        commit(session)
        return appliance

    @router.delete("/rooms/{room_id}/appliances/{appliance_id}", status_code=204)
    def delete_appliance(room_id: str, appliance_id: UUID, session: Db):
        session.delete(get_appliance(session, room_id, appliance_id))
        commit(session)
        return Response(status_code=204)

    @router.get("/rooms/{room_id}/devices", response_model=list[DeviceOutput])
    def devices(room_id: str, session: Db):
        get_room(session, room_id)
        return session.scalars(select(Device).where(Device.room_id == room_id)).all()

    @router.post("/rooms/{room_id}/devices", response_model=DeviceCredential, status_code=201)
    def provision_device(room_id: str, session: Db):
        get_room(session, room_id)
        token = secrets.token_urlsafe(32)
        device = Device(
            id=f"esp32-{uuid4().hex[:16]}", room_id=room_id, token_hash=hash_device_token(token)
        )
        session.add(device)
        commit(session)
        return DeviceCredential(id=device.id, room_id=room_id, enabled=device.enabled, token=token)

    @router.get("/rooms/{room_id}/monthly", response_model=list[MonthlyOutput])
    def monthly(room_id: str, session: Db):
        get_room(session, room_id)
        return monthly_history(session, room_id)

    return router
