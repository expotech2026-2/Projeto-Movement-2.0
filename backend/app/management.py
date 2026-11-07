import secrets
from datetime import date
from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.climate import ClimateService, ClimateUnavailable
from app.dependencies import Climate, Db, require_admin, require_user
from app.models import DEFAULT_UNIT_ID, DEFAULT_UNIT_NAME, AirConditioner, Device, Room, Unit
from app.retention import monthly_history
from app.security import hash_device_token

Admin = [Depends(require_admin)]


class UnitInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=120)
    address: str = Field(default="", max_length=160)
    city: str = Field(default="", max_length=120)


class UnitOutput(UnitInput):
    model_config = ConfigDict(from_attributes=True)
    id: str
    room_count: int = 0
    latitude: float | None = None
    longitude: float | None = None


class RoomInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    unit_id: str = Field(min_length=1, max_length=64)
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


def commit(session: Session, conflict: str = "Registro vinculado a outros dados ou já cadastrado"):
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(409, conflict) from None


def get_unit(session: Session, unit_id: str) -> Unit:
    unit = session.get(Unit, unit_id)
    if unit is None:
        raise HTTPException(404, "Unidade não encontrada")
    return unit


def get_room(session: Session, room_id: str) -> Room:
    room = session.get(Room, room_id)
    if room is None:
        raise HTTPException(404, "Sala não encontrada")
    return room


def default_unit(session: Session) -> Unit:
    unit = session.get(Unit, DEFAULT_UNIT_ID)
    if unit is None:
        unit = session.scalar(select(Unit).where(Unit.name == DEFAULT_UNIT_NAME))
    if unit is None:
        unit = Unit(id=DEFAULT_UNIT_ID, name=DEFAULT_UNIT_NAME)
        session.add(unit)
        session.flush()
    return unit


def locate_unit(unit: Unit, climate: ClimateService) -> None:
    """Grava as coordenadas da cidade, usadas para buscar a temperatura externa."""
    if not unit.city:
        unit.latitude = unit.longitude = None
        return
    try:
        place = climate.locate(unit.city)
    except ClimateUnavailable:
        raise HTTPException(
            503, "Serviço de localização indisponível; tente de novo em instantes"
        ) from None
    if place is None:
        raise HTTPException(422, "Cidade não encontrada")
    unit.latitude, unit.longitude = place.latitude, place.longitude


def create_management_router() -> APIRouter:
    router = APIRouter(dependencies=[Depends(require_user)], tags=["Unidades e salas"])

    def unit_output(unit: Unit, room_count: int) -> UnitOutput:
        return UnitOutput(
            id=unit.id,
            name=unit.name,
            address=unit.address,
            city=unit.city,
            latitude=unit.latitude,
            longitude=unit.longitude,
            room_count=room_count,
        )

    def room_count(session: Session, unit_id: str) -> int:
        return session.scalar(select(func.count()).where(Room.unit_id == unit_id))

    @router.get("/units", response_model=list[UnitOutput])
    def units(session: Db):
        counts = select(Room.unit_id, func.count().label("rooms")).group_by(Room.unit_id).subquery()
        rows = session.execute(
            select(Unit, func.coalesce(counts.c.rooms, 0))
            .outerjoin(counts, counts.c.unit_id == Unit.id)
            .order_by(Unit.name)
        )
        return [unit_output(unit, count) for unit, count in rows]

    @router.post("/units", response_model=UnitOutput, status_code=201, dependencies=Admin)
    def create_unit(payload: UnitInput, session: Db, climate: Climate):
        unit = Unit(id=f"unidade-{uuid4().hex[:16]}", **payload.model_dump())
        locate_unit(unit, climate)
        session.add(unit)
        commit(session, "Já existe uma unidade com este nome")
        return unit_output(unit, 0)

    @router.put("/units/{unit_id}", response_model=UnitOutput, dependencies=Admin)
    def update_unit(unit_id: str, payload: UnitInput, session: Db, climate: Climate):
        unit = get_unit(session, unit_id)
        moved = payload.city != unit.city or (unit.city and unit.latitude is None)
        for field, value in payload.model_dump().items():
            setattr(unit, field, value)
        if moved:
            locate_unit(unit, climate)
        commit(session, "Já existe uma unidade com este nome")
        return unit_output(unit, room_count(session, unit.id))

    @router.delete("/units/{unit_id}", status_code=204, dependencies=Admin)
    def delete_unit(unit_id: str, session: Db):
        unit = get_unit(session, unit_id)
        if room_count(session, unit.id):
            raise HTTPException(409, "Mova ou exclua as salas antes de excluir a unidade")
        session.delete(unit)
        commit(session)
        return Response(status_code=204)

    @router.get("/rooms", response_model=list[RoomOutput])
    def rooms(session: Db, unit_id: Annotated[str | None, Query(max_length=64)] = None):
        query = select(Room).order_by(Room.name, Room.id)
        if unit_id:
            query = query.where(Room.unit_id == unit_id)
        return session.scalars(query).all()

    def require_unit(session: Session, unit_id: str):
        if session.get(Unit, unit_id) is None:
            raise HTTPException(422, "Unidade não encontrada")

    @router.post("/rooms", response_model=RoomOutput, status_code=201, dependencies=Admin)
    def create_room(payload: RoomInput, session: Db):
        require_unit(session, payload.unit_id)
        room = Room(id=f"sala-{uuid4().hex[:16]}", **payload.model_dump())
        session.add(room)
        commit(session)
        return room

    @router.put("/rooms/{room_id}", response_model=RoomOutput, dependencies=Admin)
    def update_room(room_id: str, payload: RoomInput, session: Db):
        room = get_room(session, room_id)
        require_unit(session, payload.unit_id)
        for field, value in payload.model_dump().items():
            setattr(room, field, value)
        commit(session)
        return room

    @router.delete("/rooms/{room_id}", status_code=204, dependencies=Admin)
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

    @router.post(
        "/rooms/{room_id}/appliances",
        response_model=ApplianceOutput,
        status_code=201,
        dependencies=Admin,
    )
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

    @router.put(
        "/rooms/{room_id}/appliances/{appliance_id}",
        response_model=ApplianceOutput,
        dependencies=Admin,
    )
    def update_appliance(room_id: str, appliance_id: UUID, payload: ApplianceInput, session: Db):
        appliance = get_appliance(session, room_id, appliance_id)
        for field, value in payload.model_dump().items():
            setattr(appliance, field, value)
        commit(session)
        return appliance

    @router.delete(
        "/rooms/{room_id}/appliances/{appliance_id}", status_code=204, dependencies=Admin
    )
    def delete_appliance(room_id: str, appliance_id: UUID, session: Db):
        session.delete(get_appliance(session, room_id, appliance_id))
        commit(session)
        return Response(status_code=204)

    @router.get("/rooms/{room_id}/devices", response_model=list[DeviceOutput])
    def devices(room_id: str, session: Db):
        get_room(session, room_id)
        return session.scalars(select(Device).where(Device.room_id == room_id)).all()

    @router.post(
        "/rooms/{room_id}/devices",
        response_model=DeviceCredential,
        status_code=201,
        dependencies=Admin,
    )
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
